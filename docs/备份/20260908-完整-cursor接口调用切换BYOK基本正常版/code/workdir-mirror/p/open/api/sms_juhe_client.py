"""
聚合数据短信 API 客户端
文档: https://www.juhe.cn/docs/api/id/54
"""
import json
import logging
import httpx

logger = logging.getLogger(__name__)

JUHE_API = "https://v.juhe.cn/sms/send"

# 服务级错误码含义
JUHE_ERROR_MAP: dict[int, str] = {
    0: "发送成功",
    205401: "错误的手机号码",
    205402: "错误的短信模板ID",
    205403: "网络错误，请重试",
    205404: "发送失败（见reason）",
    205405: "号码异常/发送过于频繁",
    205406: "不被支持的模板",
    205407: "批量号码超限",
    205408: "库存次数不足",
    205409: "系统繁忙",
    205410: "请求方法错误",
    -1: "请求异常",
}


async def send_sms_juhe(
    *,
    app_key: str,
    mobile: str,
    tpl_id: str,
    tpl_vars: dict[str, str],
    timeout_s: float = 15.0,
) -> tuple[bool, str, str]:
    """
    发送聚合数据短信验证码。

    Args:
        app_key: 聚合数据 AppKey
        mobile: 手机号
        tpl_id: 短信模板ID（聚合平台审核通过）
        tpl_vars: 模板变量字典，如 {"code": "123456"}
        timeout_s: 超时秒数

    Returns:
        (ok, raw_body, message)
    """
    vars_json = json.dumps({k: str(v) for k, v in (tpl_vars or {}).items()})

    data = {
        "key": app_key,
        "mobile": mobile,
        "tpl_id": str(tpl_id),
        "vars": vars_json,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                JUHE_API,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            raw = (r.text or "").strip()
    except Exception as e:
        logger.warning("juhe sms request failed mobile=%s err=%s", mobile[:3] + "****", e)
        return False, "", f"请求异常: {e}"

    try:
        j = json.loads(raw)
    except json.JSONDecodeError:
        return False, raw, f"响应解析失败: {raw[:200]}"

    code = int(j.get("error_code") or -1)
    reason = str(j.get("reason") or "").strip()
    msg = reason or JUHE_ERROR_MAP.get(code, f"错误码 {code}")
    ok = code == 0

    if not ok:
        logger.warning("juhe sms send failed mobile=%s error_code=%s reason=%s", mobile[:3] + "****", code, reason)

    return ok, raw, msg
