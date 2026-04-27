from __future__ import annotations

import base64
import json
import os
import time
from typing import Any
from urllib.parse import quote

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_PRIV_KEY_PEM: str | None = None
_PRIV_KEY_PATH: str | None = None


def _normalize_pem(text: str) -> str:
    """
    Normalize PEM text copied from consoles/admin UI.
    - Accept single-line text containing literal "\\n"
    - Normalize CRLF to LF
    """
    s = (text or "").strip()
    if not s:
        return ""
    # Common: pasted as a single line with "\n" escapes.
    if "\\n" in s and "-----BEGIN" in s and "\n" not in s:
        s = s.replace("\\n", "\n")
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    return s


def _load_private_key_pem(path: str) -> str:
    global _PRIV_KEY_PEM, _PRIV_KEY_PATH
    path = os.path.abspath(path)
    if _PRIV_KEY_PEM and _PRIV_KEY_PATH == path:
        return _PRIV_KEY_PEM
    with open(path, "r", encoding="utf-8") as f:
        _PRIV_KEY_PEM = _normalize_pem(f.read())
    _PRIV_KEY_PATH = path
    return _PRIV_KEY_PEM


def merchant_private_key_pem(s: Any) -> str:
    """优先使用库内 PEM 文本，否则读私钥路径。"""
    inline = _normalize_pem(getattr(s, "alipay_merchant_private_key_pem", None) or "")
    if inline:
        return inline
    path = str(getattr(s, "alipay_merchant_private_key_path", "") or "").strip()
    if not path:
        return ""
    return _load_private_key_pem(path)


def alipay_configured(s: Any) -> bool:
    return bool(
        (getattr(s, "alipay_app_id", "") or "").strip()
        and (getattr(s, "alipay_gateway", "") or "").strip()
        and (getattr(s, "alipay_notify_url", "") or "").strip()
        and (getattr(s, "alipay_public_key", "") or "").strip()
        and bool(merchant_private_key_pem(s).strip())
    )


def _sign_rsa2(private_key_pem: str, message: str) -> str:
    pem = _normalize_pem(private_key_pem)
    if not pem or "-----BEGIN" not in pem:
        raise RuntimeError("invalid_alipay_private_key_pem: missing PEM header/footer")
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as e:
        # Provide a crisp hint for ops/admin UI pastes.
        raise RuntimeError(
            "invalid_alipay_private_key_pem: Unable to load PEM file (often caused by missing header/footer, "
            "wrong key type, or pasting a single-line string with literal \\n)."
        ) from e
    sig = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


def _verify_rsa2(public_key_pem: str, message: str, signature_b64: str) -> bool:
    pem = _normalize_pem(public_key_pem)
    if not pem or "-----BEGIN" not in pem:
        return False
    try:
        pub = serialization.load_pem_public_key(pem.encode("utf-8"))
    except Exception:
        return False
    sig = base64.b64decode(signature_b64.encode("utf-8"))
    try:
        pub.verify(sig, message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _canonical_kv(params: dict[str, str]) -> str:
    """按支付宝规则：按 key 字典序排序，拼接 key=value&..."""
    items: list[str] = []
    for k in sorted(params.keys()):
        v = params.get(k)
        if v is None:
            continue
        items.append(f"{k}={v}")
    return "&".join(items)


def build_wap_pay_url(
    s: Any,
    *,
    out_trade_no: str,
    subject: str,
    total_amount_yuan: str,
    return_url: str | None = None,
) -> str:
    """
    生成支付宝 WAP 支付跳转 URL（alipay.trade.wap.pay）。
    返回一个可直接 302/前端跳转的 URL。
    """
    if not alipay_configured(s):
        raise RuntimeError("Alipay is not configured")

    app_id = str(getattr(s, "alipay_app_id", "")).strip()
    gateway = str(getattr(s, "alipay_gateway", "")).strip().rstrip("?")
    notify_url = str(getattr(s, "alipay_notify_url", "")).strip()
    charset = "utf-8"

    biz = {
        "out_trade_no": out_trade_no,
        "total_amount": str(total_amount_yuan),
        "subject": subject[:128],
        "product_code": "QUICK_WAP_WAY",
    }

    params: dict[str, str] = {
        "app_id": app_id,
        "method": "alipay.trade.wap.pay",
        "format": "JSON",
        "charset": charset,
        "sign_type": "RSA2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "version": "1.0",
        "notify_url": notify_url,
        "biz_content": json.dumps(biz, ensure_ascii=False, separators=(",", ":")),
    }
    if return_url:
        params["return_url"] = str(return_url).strip()

    sign_src = _canonical_kv(params)
    pem = merchant_private_key_pem(s)
    params["sign"] = _sign_rsa2(pem, sign_src)

    qs = "&".join([f"{quote(k)}={quote(v)}" for k, v in params.items()])
    return f"{gateway}?{qs}"


def verify_notify(
    s: Any,
    *,
    form: dict[str, str],
) -> tuple[bool, str | None]:
    """支付宝异步通知验签（RSA2）。返回 (ok, error_message)。"""
    public_key = _normalize_pem(str(getattr(s, "alipay_public_key", "") or ""))
    if not public_key:
        return False, "missing_alipay_public_key"

    sign = (form.get("sign") or "").strip()
    sign_type = (form.get("sign_type") or "RSA2").strip().upper()
    if not sign or sign_type != "RSA2":
        return False, "missing_or_invalid_sign"

    data = {k: str(v) for k, v in form.items() if k not in ("sign", "sign_type") and v is not None}
    msg = _canonical_kv(data)
    if not _verify_rsa2(public_key, msg, sign):
        return False, "invalid_signature"
    return True, None

