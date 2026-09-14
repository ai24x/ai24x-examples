"""
本地短信直发（106 网关）+ 用户 OTP 内存存储。
2026-08-04 雷总拍板：行情官(a.ai24x.com) 短信独立直发，不依赖主站(04)。

启用方式（admin_config 表）：
  sms_active_provider = local
  sms_106_endpoint / sms_106_account / sms_106_password / sms_106_sign_name / sms_106_template

与 api/（主站）同协议：http://sms.106jiekou.com/utf8/sms.aspx?account=..&password=..&mobile=..&content=..
返回纯文本状态码：100=成功（详见 STATUS_MESSAGES）。
"""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STATUS_MESSAGES: dict[str, str] = {
    "100": "发送成功",
    "101": "验证失败",
    "102": "手机号码格式不正确",
    "103": "会员级别不够",
    "104": "内容未审核",
    "105": "内容过多",
    "106": "账户余额不足",
    "107": "IP 受限",
    "108": "手机号码发送太频繁",
    "109": "帐号被锁定",
    "110": "发送通道不正确",
    "111": "当前时间段禁止短信发送",
    "112": "账号未认证",
    "120": "系统升级",
}


def normalize_mobile(mobile: str) -> str:
    s = "".join(c for c in (mobile or "").strip() if c.isdigit() or c == "+")
    if s.startswith("+86"):
        s = s[3:]
    if s.startswith("86") and len(s) == 13:
        s = s[2:]
    return s


def generate_numeric_code(digits: int = 6) -> str:
    if digits < 4 or digits > 8:
        digits = 6
    upper = 10**digits
    lower = 10 ** (digits - 1)
    n = secrets.randbelow(upper - lower) + lower
    return str(n)


def send_sms_106_sync(
    *,
    endpoint: str,
    account: str,
    password: str,
    mobile: str,
    content: str,
    sign_name: str | None = None,
    timeout_s: float = 15.0,
) -> tuple[bool, str, str]:
    """同步版 106 网关提交（a1 路由为同步 FastAPI，故用 httpx.Client）。"""
    url = (endpoint or "").strip()
    params: dict[str, Any] = {
        "account": account,
        "password": password,
        "mobile": mobile,
        "content": content,
    }
    if sign_name:
        params["signName"] = sign_name

    with httpx.Client(timeout=timeout_s) as client:
        r = client.get(url, params=params)
        raw = (r.text or "").strip()

    ok = raw == "100"
    msg = STATUS_MESSAGES.get(raw, f"未知状态码: {raw}")
    if not ok:
        logger.warning("local sms send failed mobile=%s raw=%s", mobile[:3] + "****", raw)
    return ok, raw, msg


def send_sms_juhe_sync(
    *,
    app_key: str,
    mobile: str,
    tpl_id: str,
    tpl_vars: dict[str, str],
    timeout_s: float = 15.0,
) -> tuple[bool, str, str]:
    """同步版聚合数据短信：POST https://v.juhe.cn/sms/send（key/mobile/tpl_id/vars）。"""
    import json as _json

    vars_json = _json.dumps({k: str(v) for k, v in (tpl_vars or {}).items()})
    data = {"key": app_key, "mobile": mobile, "tpl_id": str(tpl_id), "vars": vars_json}
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(
                "https://v.juhe.cn/sms/send",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            raw = (r.text or "").strip()
    except Exception as e:
        return False, "", f"请求异常: {e}"
    try:
        j = _json.loads(raw)
    except Exception:
        return False, raw, f"响应解析失败: {raw[:200]}"
    code = int(j.get("error_code") or -1)
    reason = str(j.get("reason") or "").strip()
    msg = reason or f"聚合数据错误码 {code}"
    ok = code == 0
    if not ok:
        logger.warning("local juhe sms failed mobile=%s error_code=%s reason=%s", mobile[:3] + "****", code, reason)
    return ok, raw, msg


def _tc3_sign_sync(
    secret_id: str, secret_key: str, service: str, host: str, action: str,
    version: str, region: str, payload: str, timestamp: int,
) -> str:
    import hashlib, hmac
    from datetime import datetime, timezone as _tz

    date = datetime.fromtimestamp(timestamp, tz=_tz.utc).strftime("%Y-%m-%d")
    canonical_headers = f"content-type:application/json\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(["POST", "/", "", canonical_headers, signed_headers, hashed_payload])
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join(["TC3-HMAC-SHA256", str(timestamp), credential_scope, hashed_canonical])

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _sign(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def send_sms_tencent_sync(
    *,
    secret_id: str, secret_key: str, sdk_app_id: str, sign_name: str,
    template_id: str, template_params: list[str], phone: str,
    region: str = "ap-guangzhou", timeout_s: float = 15.0,
) -> tuple[bool, str, str]:
    """同步版腾讯云短信 SendSms（TC3-HMAC-SHA256）。"""
    import json as _json
    import time as _time

    phone_e164 = f"+86{phone}" if not phone.startswith("+") else phone
    body: dict = {
        "PhoneNumberSet": [phone_e164],
        "SmsSdkAppId": sdk_app_id,
        "SignName": sign_name,
        "TemplateId": template_id,
    }
    if template_params:
        body["TemplateParamSet"] = [str(p) for p in template_params]
    payload = _json.dumps(body)
    ts = int(_time.time())
    auth = _tc3_sign_sync(
        secret_id=secret_id, secret_key=secret_key, service="sms",
        host="sms.tencentcloudapi.com", action="SendSms", version="2021-01-11",
        region=region, payload=payload, timestamp=ts,
    )
    headers = {
        "Content-Type": "application/json", "Host": "sms.tencentcloudapi.com",
        "X-TC-Action": "SendSms", "X-TC-Version": "2021-01-11",
        "X-TC-Timestamp": str(ts), "X-TC-Region": region, "Authorization": auth,
    }
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(f"https://sms.tencentcloudapi.com/", content=payload, headers=headers)
            raw = (r.text or "").strip()
    except Exception as e:
        return False, "", f"请求异常: {e}"
    try:
        j = _json.loads(raw)
    except Exception:
        return False, raw, f"响应解析失败: {raw[:200]}"
    resp = j.get("Response", j)
    status_set = resp.get("SendStatusSet", [])
    if not status_set:
        err = resp.get("Error", {})
        return False, raw, str(err.get("Message") or err.get("Code") or "未知错误")
    st = status_set[0]
    code = st.get("Code", "")
    ok = code == "Ok"
    msg = "发送成功" if ok else str(st.get("Message") or f"腾讯云错误码 {code}")
    if not ok:
        logger.warning("local tencent sms failed phone=%s code=%s", phone[:3] + "****", code)
    return ok, raw, msg


# ---- 用户 OTP（进程内，生产可后续换 Redis/DB） ----
_store: dict[str, tuple[str, float]] = {}
_verify_fails: dict[str, list[float]] = {}
_VERIFY_MAX_FAILS = 5


def _key(phone: str, purpose: str) -> str:
    return f"{normalize_mobile(phone)}:{purpose.strip().lower()}"


def store_otp(phone: str, purpose: str, code: str, ttl_s: float = 300.0) -> None:
    _store[_key(phone, purpose)] = (str(code).strip(), time.time() + float(ttl_s))


def verify_and_consume_otp(phone: str, purpose: str, code: str) -> bool:
    import hmac

    k = _key(phone, purpose)
    tup = _store.get(k)
    if not tup:
        return False
    stored, exp = tup
    now = time.time()
    if now > exp:
        try:
            del _store[k]
        except KeyError:
            pass
        _verify_fails.pop(k, None)
        return False
    fails = [t for t in (_verify_fails.get(k) or []) if now - t < 600.0]
    if len(fails) >= _VERIFY_MAX_FAILS:
        # 防爆破：连续错误超限即作废验证码，需重新获取
        try:
            del _store[k]
        except KeyError:
            pass
        _verify_fails.pop(k, None)
        return False
    if not hmac.compare_digest(str(stored or "").encode("utf-8"), str(code or "").strip().encode("utf-8")):
        _verify_fails[k] = fails + [now]
        return False
    _verify_fails.pop(k, None)
    del _store[k]
    return True


# ---- 发送冷却（同号） ----
_last_sent_at: dict[str, float] = {}


def check_send_cooldown(mobile: str, cooldown_s: float) -> tuple[bool, float | None]:
    now = time.time()
    key = normalize_mobile(mobile)
    last = _last_sent_at.get(key)
    if last is None:
        return True, None
    elapsed = now - last
    if elapsed >= cooldown_s:
        return True, None
    return False, max(0.0, cooldown_s - elapsed)


def mark_sent(mobile: str) -> None:
    _last_sent_at[normalize_mobile(mobile)] = time.time()


DEFAULT_TEMPLATE = "您的验证码是：{code}。请不要把验证码泄露给其他人。如非本人操作，可不用理会！"


def send_local_sms(*, cfg, mobile: str, purpose: str, cooldown_s: float = 60.0) -> tuple[bool, str, str | None]:
    """本地直发：校验手机号 → 冷却 → 生成验证码 → 存 OTP → 调通道（juhe/tencent/106）。

    通道选择：cfg.sms_active_provider == "juhe" → 聚合数据；"tencent" → 腾讯云；否则 106。
    返回 (ok, msg, dev_code)；dev_code 生产恒为 None。
    """
    mob = normalize_mobile(mobile)
    if len(mob) != 11 or not mob.isdigit():
        return False, "手机号格式不正确，请填写 11 位手机号", None

    allowed, remain = check_send_cooldown(mob, float(cooldown_s))
    if not allowed:
        return False, f"发送过于频繁，请 {int(remain or 0) + 1} 秒后再试", None

    provider = (cfg.sms_active_provider or "local").strip().lower()
    code = generate_numeric_code(6)
    ok, msg = _deliver_code(cfg, mob, code)
    if ok:
        store_otp(mob, purpose, code, ttl_s=300.0)
        mark_sent(mob)
    else:
        logger.warning("local sms send failed provider=%s purpose=%s msg=%s", provider, purpose, msg)
    return ok, msg, None


def _deliver_code(cfg, mob: str, code: str) -> tuple[bool, str]:
    """按通道发送指定验证码（juhe/tencent/106），返回 (ok, msg)。"""
    provider = (cfg.sms_active_provider or "local").strip().lower()
    if provider == "juhe":
        app_key = (cfg.sms_juhe_key or "").strip()
        tpl_id = (cfg.sms_juhe_template_id or "").strip()
        if not app_key or not tpl_id:
            return False, "短信服务未配置（juhe key/tpl_id），请联系管理员"
        ok, _raw, msg = send_sms_juhe_sync(app_key=app_key, mobile=mob, tpl_id=tpl_id, tpl_vars={"code": code})
        return ok, msg
    if provider == "tencent":
        sid = (cfg.sms_tencent_secret_id or "").strip()
        skey = (cfg.sms_tencent_secret_key or "").strip()
        app = (cfg.sms_tencent_sdk_app_id or "").strip()
        sign = (cfg.sms_tencent_sign or "").strip()
        tpl = (cfg.sms_tencent_template_id or "").strip()
        if not (sid and skey and app and sign and tpl):
            return False, "短信服务未配置（tencent 参数不全），请联系管理员"
        ok, _raw, msg = send_sms_tencent_sync(
            secret_id=sid, secret_key=skey, sdk_app_id=app, sign_name=sign,
            template_id=tpl, template_params=[code], phone=mob,
        )
        return ok, msg
    # local / 106
    if not (cfg.sms_106_account or "").strip() or not (cfg.sms_106_password or "").strip():
        logger.error("local sms not configured: sms_106_account/password missing in admin_config")
        return False, "短信服务未配置，请联系管理员"
    template = (cfg.sms_106_template or "").strip() or DEFAULT_TEMPLATE
    try:
        content = template.format(code=code)
    except Exception:
        content = DEFAULT_TEMPLATE.format(code=code)
    ok, _raw, msg = send_sms_106_sync(
        endpoint=(cfg.sms_106_endpoint or "").strip() or "http://sms.106jiekou.com/utf8/sms.aspx",
        account=(cfg.sms_106_account or "").strip(),
        password=(cfg.sms_106_password or "").strip(),
        mobile=mob,
        content=content,
        sign_name=(cfg.sms_106_sign_name or "").strip() or None,
    )
    return ok, msg


def send_local_sms_code(*, cfg, mobile: str, code: str) -> tuple[bool, str]:
    """发送指定验证码（管理后台 OTP 等场景），不写入用户 OTP 存储。"""
    mob = normalize_mobile(mobile)
    if len(mob) != 11 or not mob.isdigit():
        return False, "手机号格式不正确，请填写 11 位手机号"
    allowed, remain = check_send_cooldown(mob, 60.0)
    if not allowed:
        return False, f"发送过于频繁，请 {int(remain or 0) + 1} 秒后再试"
    ok, msg = _deliver_code(cfg, mob, str(code or "")[:6])
    if ok:
        mark_sent(mob)
    else:
        logger.warning("local sms send code failed msg=%s", msg)
    return ok, msg
