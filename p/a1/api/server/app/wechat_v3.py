"""
WeChat Pay API v3 helpers (Native 下单 + 支付结果通知验签与解密).

后续支付宝 / PayPal 建议独立模块，通过 pay_orders.channel 分流。
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import string
import time
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PLATFORM_CERT_CACHE: dict[str, str] = {}
_PLATFORM_CERT_AT: float = 0.0
_CERT_CACHE_TTL_S = 3600.0
_PRIV_KEY_PEM: str | None = None
_PRIV_KEY_PATH: str | None = None


def _normalize_pem(text: Any) -> str:
    """
    Normalize PEM text copied from consoles/admin UI.
    - Accept single-line text containing literal "\\n"
    - Normalize CRLF to LF
    """
    try:
        s = str(text or "").strip()
    except Exception:
        s = ""
    if not s:
        return ""
    if "\\n" in s and "-----BEGIN" in s and "\n" not in s:
        s = s.replace("\\n", "\n")
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    return s


def merchant_private_key_pem(s: Any) -> str:
    """优先使用库内 PEM 文本，否则读 apiclient_key 路径。"""
    inline = _normalize_pem(getattr(s, "wechat_mch_private_key_pem", None) or "")
    if inline:
        return inline
    path = str(getattr(s, "wechat_mch_private_key_path", "") or "").strip()
    return _load_private_key_pem(path)


def wechat_pay_configured(s: Any) -> bool:
    has_pem_inline = bool((getattr(s, "wechat_mch_private_key_pem", None) or "").strip())
    has_path = bool(str(getattr(s, "wechat_mch_private_key_path", "") or "").strip())
    return bool(
        getattr(s, "wechat_mch_id", "")
        and getattr(s, "wechat_app_id", "")
        and getattr(s, "wechat_mch_serial_no", "")
        and (has_pem_inline or has_path)
        and len(str(getattr(s, "wechat_api_v3_key", "") or "")) == 32
        and getattr(s, "wechat_notify_url", "")
    )


def _load_private_key_pem(path: str) -> str:
    global _PRIV_KEY_PEM, _PRIV_KEY_PATH
    path = os.path.abspath(path)
    if _PRIV_KEY_PEM and _PRIV_KEY_PATH == path:
        return _PRIV_KEY_PEM
    with open(path, "r", encoding="utf-8") as f:
        _PRIV_KEY_PEM = _normalize_pem(f.read())
    _PRIV_KEY_PATH = path
    return _PRIV_KEY_PEM


def _sign_authorization(private_key_pem: str, message: str) -> str:
    pem = _normalize_pem(private_key_pem)
    if not pem or "-----BEGIN" not in pem:
        raise RuntimeError("invalid_wechat_private_key_pem: missing PEM header/footer")
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as e:
        raise RuntimeError(
            "invalid_wechat_private_key_pem: Unable to load PEM file (often caused by missing header/footer, "
            "wrong key type, or pasting a single-line string with literal \\n)."
        ) from e
    sig = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


def _build_auth_header(
    mchid: str,
    serial_no: str,
    private_key_pem: str,
    method: str,
    url_path: str,
    body: str,
) -> str:
    ts = str(int(time.time()))
    nonce = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    msg = f"{method.upper()}\n{url_path}\n{ts}\n{nonce}\n{body}\n"
    sig = _sign_authorization(private_key_pem, msg)
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
        f'nonce_str="{nonce}",signature="{sig}",timestamp="{ts}",serial_no="{serial_no}"'
    )


def _aes_gcm_decrypt(api_v3_key: str, nonce_b64: str, ciphertext_b64: str, associated_data: str) -> bytes:
    key = api_v3_key.encode("utf-8")
    if len(key) != 32:
        raise ValueError("APIv3 key must be 32 bytes")
    aes = AESGCM(key)
    nonce = base64.b64decode(nonce_b64)
    ct = base64.b64decode(ciphertext_b64)
    ad = associated_data.encode("utf-8") if associated_data else b""
    return aes.decrypt(nonce, ct, ad)


def _decrypt_wechat_cert_field(api_v3_key: str, enc: dict[str, Any]) -> str:
    return _aes_gcm_decrypt(
        api_v3_key,
        str(enc["nonce"]),
        str(enc["ciphertext"]),
        str(enc.get("associated_data") or ""),
    ).decode("utf-8")


def _verify_notify_signature(public_key_pem: str, timestamp: str, nonce: str, body: str, signature_b64: str) -> bool:
    pub = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    message = f"{timestamp}\n{nonce}\n{body}\n".encode("utf-8")
    sig = base64.b64decode(signature_b64)
    try:
        pub.verify(sig, message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _public_key_pem_from_certificate(cert_pem: str) -> str:
    cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    pub = cert.public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


async def _fetch_platform_certificates(s: Any) -> dict[str, str]:
    """serial_no -> PEM public key (not full cert)."""
    global _PLATFORM_CERT_CACHE, _PLATFORM_CERT_AT
    now = time.time()
    if _PLATFORM_CERT_CACHE and now - _PLATFORM_CERT_AT < _CERT_CACHE_TTL_S:
        return _PLATFORM_CERT_CACHE

    path = "/v3/certificates"
    url = f"{s.wechat_pay_host}{path}"
    pem = merchant_private_key_pem(s)
    auth = _build_auth_header(s.wechat_mch_id, s.wechat_mch_serial_no, pem, "GET", path, "")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers={"Authorization": auth, "Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    out: dict[str, str] = {}
    for item in data.get("data") or []:
        sn = str(item.get("serial_no") or "")
        enc = item.get("encrypt_certificate") or {}
        if not sn or not isinstance(enc, dict):
            continue
        cert_pem = _decrypt_wechat_cert_field(s.wechat_api_v3_key, enc)
        out[sn] = _public_key_pem_from_certificate(cert_pem)
    if not out:
        raise RuntimeError("no platform certificates from WeChat")
    _PLATFORM_CERT_CACHE = out
    _PLATFORM_CERT_AT = now
    return out


async def native_create_order(
    s: Any,
    *,
    out_trade_no: str,
    description: str,
    amount_fen: int,
) -> dict[str, Any]:
    if not wechat_pay_configured(s):
        raise RuntimeError("WeChat Pay is not configured")
    path = "/v3/pay/transactions/native"
    url = f"{s.wechat_pay_host}{path}"
    body_obj = {
        "appid": s.wechat_app_id,
        "mchid": s.wechat_mch_id,
        "description": description[:127],
        "out_trade_no": out_trade_no,
        "notify_url": s.wechat_notify_url,
        "amount": {"total": int(amount_fen), "currency": "CNY"},
    }
    body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    pem = merchant_private_key_pem(s)
    auth = _build_auth_header(s.wechat_mch_id, s.wechat_mch_serial_no, pem, "POST", path, body)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            url,
            content=body.encode("utf-8"),
            headers={
                "Authorization": auth,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"wechat native error {r.status_code}: {payload}")
    return payload


async def query_transaction_by_out_trade_no(s: Any, *, out_trade_no: str) -> dict[str, Any]:
    """
    主动查询微信订单状态（兜底：notify 未达时可用）。

    返回字段通常包含 trade_state / transaction_id / out_trade_no / amount 等。
    """
    if not wechat_pay_configured(s):
        raise RuntimeError("WeChat Pay is not configured")
    otn = str(out_trade_no or "").strip()
    if not otn:
        raise ValueError("missing out_trade_no")

    path = f"/v3/pay/transactions/out-trade-no/{otn}?mchid={s.wechat_mch_id}"
    url = f"{s.wechat_pay_host}{path}"
    pem = merchant_private_key_pem(s)
    auth = _build_auth_header(s.wechat_mch_id, s.wechat_mch_serial_no, pem, "GET", path, "")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            url,
            headers={
                "Authorization": auth,
                "Accept": "application/json",
            },
        )
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text}
    if r.status_code >= 400:
        raise RuntimeError(f"wechat query error {r.status_code}: {payload}")
    return payload


async def parse_payment_notify(
    s: Any,
    *,
    headers: dict[str, str],
    body_str: str,
) -> dict[str, Any]:
    """
    验签 + 解密 resource，返回交易字段（含 out_trade_no / transaction_id / amount / trade_state）。
    """
    h = {k.lower(): v for k, v in headers.items()}
    if s.wechat_notify_skip_verify:
        root = json.loads(body_str)
        resource = root.get("resource") or {}
        pt = _aes_gcm_decrypt(
            s.wechat_api_v3_key,
            str(resource["nonce"]),
            str(resource["ciphertext"]),
            str(resource.get("associated_data") or ""),
        ).decode("utf-8")
        return json.loads(pt)

    serial = str(h.get("wechatpay-serial") or "")
    signature = str(h.get("wechatpay-signature") or "")
    ts = str(h.get("wechatpay-timestamp") or "")
    nonce = str(h.get("wechatpay-nonce") or "")
    if not (serial and signature and ts and nonce):
        raise ValueError("missing wechatpay signature headers")

    certs = await _fetch_platform_certificates(s)
    pub_pem = certs.get(serial)
    if not pub_pem:
        # refresh cache once if serial unknown (key rotation)
        global _PLATFORM_CERT_AT
        _PLATFORM_CERT_AT = 0.0
        certs = await _fetch_platform_certificates(s)
        pub_pem = certs.get(serial)
    if not pub_pem:
        raise ValueError("unknown wechatpay certificate serial")

    if not _verify_notify_signature(pub_pem, ts, nonce, body_str, signature):
        raise ValueError("invalid notify signature")

    root = json.loads(body_str)
    resource = root.get("resource") or {}
    pt = _aes_gcm_decrypt(
        s.wechat_api_v3_key,
        str(resource["nonce"]),
        str(resource["ciphertext"]),
        str(resource.get("associated_data") or ""),
    ).decode("utf-8")
    return json.loads(pt)
