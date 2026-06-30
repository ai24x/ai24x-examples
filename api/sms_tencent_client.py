"""
腾讯云短信 API 客户端（SendSms）
文档: https://cloud.tencent.com/document/product/382/55981
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

TENCENT_HOST = "sms.tencentcloudapi.com"
TENCENT_SERVICE = "sms"
TENCENT_ACTION = "SendSms"
TENCENT_VERSION = "2021-01-11"

# 腾讯云短信错误码 → 中文友好提示
TENCENT_ERROR_MAP: dict[str, str] = {
    "LimitExceeded.PhoneNumberDailyLimit":        "该手机号今日发送次数已达上限，请明天再试",
    "LimitExceeded.PhoneNumberThirtySecondLimit": "发送过于频繁，请稍后再试",
    "LimitExceeded.PhoneNumberOneHourLimit":      "该手机号每小时发送次数已达上限，请稍后再试",
    "LimitExceeded.PhoneNumberTenSecondLimit":    "发送过于频繁，请稍后再试",
    "FailedOperation.PhoneNumberInBlacklist":     "该手机号无法接收短信（可能被运营商拉黑）",
    "FailedOperation.SignatureIncorrectOrUnapproved": "短信签名未审批通过，请联系管理员",
    "FailedOperation.TemplateIncorrectOrUnapproved":  "短信模板未审批通过，请联系管理员",
    "InvalidParameterValue.TemplateIdNotExist":   "短信模板ID配置错误，请在后台检查",
    "AuthFailure.UnauthorizedOperation":          "API密钥权限不足，需在腾讯云CAM控制台关联短信权限",
    "AuthFailure.SignatureFailure":               "API密钥验证失败，请检查SecretId/SecretKey是否正确",
    "UnauthorizedOperation.SmsMessagesQpsOverLimit": "短信发送频率超出QPS上限，请稍后再试",
    "FailedOperation.InsufficientBalanceInSmsPackage": "短信套餐余额不足，请充值",
}


def _tc3_sign(
    secret_id: str,
    secret_key: str,
    service: str,
    host: str,
    action: str,
    version: str,
    region: str,
    payload: str,
    timestamp: int,
) -> tuple[str, str]:
    """Generate TC3-HMAC-SHA256 authorization header."""
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

    # 1. Canonical Request
    canonical_headers = f"content-type:application/json\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = "\n".join([
        "POST", "/", "",
        canonical_headers,
        signed_headers,
        hashed_payload,
    ])

    # 2. String to Sign
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join([
        "TC3-HMAC-SHA256",
        str(timestamp),
        credential_scope,
        hashed_canonical,
    ])

    # 3. Signature
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _sign(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    # 4. Authorization header
    authorization = (
        f"TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    return authorization, date


async def send_sms_tencent(
    *,
    secret_id: str,
    secret_key: str,
    sdk_app_id: str,
    sign_name: str,
    template_id: str,
    template_params: list[str],
    phone: str,
    region: str = "ap-guangzhou",
    timeout_s: float = 15.0,
) -> tuple[bool, str, str]:
    """
    发送腾讯云短信验证码。

    Args:
        secret_id: 腾讯云 API SecretId
        secret_key: 腾讯云 API SecretKey
        sdk_app_id: 短信应用 SDK AppID
        sign_name: 短信签名（已审核）
        template_id: 模板 ID（已审核）
        template_params: 模板变量值列表，如 ["123456"]
        phone: 手机号（国内 11 位）
        region: 地域
        timeout_s: 超时秒数

    Returns:
        (ok, raw_body, message)
    """
    # E.164 format
    phone_e164 = f"+86{phone}" if not phone.startswith("+") else phone

    body: dict = {
        "PhoneNumberSet": [phone_e164],
        "SmsSdkAppId": sdk_app_id,
        "SignName": sign_name,
        "TemplateId": template_id,
    }
    if template_params:
        body["TemplateParamSet"] = [str(p) for p in template_params]

    payload = json.dumps(body)
    ts = int(time.time())
    auth, _date = _tc3_sign(
        secret_id=secret_id,
        secret_key=secret_key,
        service=TENCENT_SERVICE,
        host=TENCENT_HOST,
        action=TENCENT_ACTION,
        version=TENCENT_VERSION,
        region=region,
        payload=payload,
        timestamp=ts,
    )

    headers = {
        "Content-Type": "application/json",
        "Host": TENCENT_HOST,
        "X-TC-Action": TENCENT_ACTION,
        "X-TC-Version": TENCENT_VERSION,
        "X-TC-Timestamp": str(ts),
        "X-TC-Region": region,
        "Authorization": auth,
    }

    url = f"https://{TENCENT_HOST}/"
    raw = ""
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(url, content=payload, headers=headers)
            raw = (r.text or "").strip()
    except Exception as e:
        logger.warning("tencent sms request failed phone=%s err=%s", phone[:3] + "****", e)
        return False, "", f"请求异常: {e}"

    try:
        j = json.loads(raw)
    except json.JSONDecodeError:
        return False, raw, f"响应解析失败: {raw[:200]}"

    resp = j.get("Response", j)
    status_set = resp.get("SendStatusSet", [])
    req_id = resp.get("RequestId", "") or resp.get("Error", {}).get("RequestId", "")

    if not status_set:
        err_info = resp.get("Error", {})
        code = err_info.get("Code", "UnknownError")
        raw_msg = err_info.get("Message", "未知错误")
        msg = TENCENT_ERROR_MAP.get(code, raw_msg)
        logger.warning("tencent sms API error code=%s msg=%s reqId=%s", code, msg, req_id)
        return False, raw, msg

    st = status_set[0]
    code = st.get("Code", "")
    raw_msg = st.get("Message", "")
    msg = TENCENT_ERROR_MAP.get(code, raw_msg) if not (code == "Ok") else "发送成功"
    ok = code == "Ok"

    if not ok:
        logger.warning(
            "tencent sms send failed phone=%s code=%s msg=%s reqId=%s",
            phone[:3] + "****", code, msg, req_id,
        )

    return ok, raw, msg
