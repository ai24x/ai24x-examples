#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 AI行情官(a1) 读取商户凭证，供 Token 支付复用。

可共用：商户号 / AppId / 序列号 / API v3 / 私钥文件或 PEM / 支付宝密钥
不可共用：回调 URL（Token 必须用 TOKEN_*_NOTIFY_URL）

来源优先级：
1) a1 admin_config（管理后台已配的那套）
2) a1 api/server/.env 的 AI24X_WECHAT_* / AI24X_ALIPAY_*
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

API_DIR = Path(__file__).resolve().parent
REPO = API_DIR.parent
A1_SERVER = REPO / "p" / "a1" / "api" / "server"

# a1 admin_config / 逻辑名 -> 供 pay_settings_ns 合并的字段名
A1_TO_CORE = {
    "wechat_mch_id": "wechat_mch_id",
    "wechat_app_id": "wechat_app_id",
    "wechat_mch_serial_no": "wechat_mch_serial_no",
    "wechat_mch_private_key_path": "wechat_mch_private_key_path",
    "wechat_mch_private_key_pem": "wechat_mch_private_key_pem",
    "wechat_api_v3_key": "wechat_api_v3_key",
    "wechat_pay_host": "wechat_pay_host",
    "alipay_app_id": "alipay_app_id",
    "alipay_gateway": "alipay_gateway",
    "alipay_merchant_private_key_path": "alipay_merchant_private_key_path",
    "alipay_merchant_private_key_pem": "alipay_merchant_private_key_pem",
    "alipay_public_key": "alipay_public_key",
}

ENV_MAP = {
    "AI24X_WECHAT_MCH_ID": "wechat_mch_id",
    "AI24X_WECHAT_APP_ID": "wechat_app_id",
    "AI24X_WECHAT_MCH_SERIAL_NO": "wechat_mch_serial_no",
    "AI24X_WECHAT_MCH_PRIVATE_KEY_PATH": "wechat_mch_private_key_path",
    "AI24X_WECHAT_MCH_PRIVATE_KEY_PEM": "wechat_mch_private_key_pem",
    "AI24X_WECHAT_API_V3_KEY": "wechat_api_v3_key",
    "AI24X_WECHAT_PAY_HOST": "wechat_pay_host",
    "AI24X_ALIPAY_APP_ID": "alipay_app_id",
    "AI24X_ALIPAY_GATEWAY": "alipay_gateway",
    "AI24X_ALIPAY_MERCHANT_PRIVATE_KEY_PATH": "alipay_merchant_private_key_path",
    "AI24X_ALIPAY_MERCHANT_PRIVATE_KEY_PEM": "alipay_merchant_private_key_pem",
    "AI24X_ALIPAY_PUBLIC_KEY": "alipay_public_key",
}

_CACHE: dict[str, str] | None = None
_CACHE_AT = 0.0
_CACHE_TTL_S = 60.0


def _bad(v: str) -> bool:
    s = (v or "").strip()
    return (not s) or s == "***" or s.startswith("***")


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v
    return out


def _resolve_path(raw: str) -> str:
    p = (raw or "").strip().strip('"').strip("'")
    if not p:
        return ""
    path = Path(p)
    if not path.is_absolute():
        path = (A1_SERVER / p).resolve()
    return str(path)


def _from_a1_admin_config() -> dict[str, str]:
    if not A1_SERVER.exists():
        return {}
    try:
        import os
        import sys

        root = str(A1_SERVER)
        if root not in sys.path:
            sys.path.insert(0, root)
        cwd = os.getcwd()
        try:
            os.chdir(root)
            from app import db  # type: ignore

            raw = dict(db.admin_config_get_all() or {})
        finally:
            try:
                os.chdir(cwd)
            except OSError:
                pass
    except Exception as e:
        logger.info("a1 admin_config unavailable: %s", e)
        return {}

    out: dict[str, str] = {}
    for a1k, corek in A1_TO_CORE.items():
        v = str(raw.get(a1k) or "").strip()
        if _bad(v):
            continue
        if a1k.endswith("_path"):
            v = _resolve_path(v)
        out[corek] = v
    return out


def _from_a1_dotenv() -> dict[str, str]:
    env = _parse_dotenv(A1_SERVER / ".env")
    out: dict[str, str] = {}
    for ek, corek in ENV_MAP.items():
        v = str(env.get(ek) or "").strip()
        if _bad(v):
            continue
        if corek.endswith("_path"):
            v = _resolve_path(v)
        out[corek] = v
    # 默认同目录 apiclient_key.pem
    default_pem = A1_SERVER / "apiclient_key.pem"
    if "wechat_mch_private_key_path" not in out and default_pem.exists():
        out["wechat_mch_private_key_path"] = str(default_pem.resolve())
    return out


def load_a1_merchant_credentials(*, force: bool = False) -> dict[str, str]:
    """返回 core 字段名的商户凭证（不含任何 notify/return URL）。"""
    global _CACHE, _CACHE_AT
    now = time.time()
    if not force and _CACHE is not None and (now - _CACHE_AT) < _CACHE_TTL_S:
        return dict(_CACHE)

    merged: dict[str, str] = {}
    # dotenv 打底，admin_config 覆盖（后台改动能生效）
    for src in (_from_a1_dotenv(), _from_a1_admin_config()):
        for k, v in src.items():
            if not _bad(v):
                merged[k] = v

    _CACHE = dict(merged)
    _CACHE_AT = now
    if merged:
        logger.info(
            "a1 pay credentials loaded: %s",
            ",".join(sorted(k for k in merged if not k.endswith("_pem"))),
        )
    return dict(merged)


def merge_a1_into_pay_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """对空 / *** / 明显损坏字段用 a1 凭证填充；绝不写入 notify。"""
    a1 = load_a1_merchant_credentials()
    if not a1:
        return kwargs
    out = dict(kwargs)

    def need_fill(key: str, cur: str) -> bool:
        if _bad(cur):
            return True
        if key == "wechat_api_v3_key" and len(cur) != 32:
            return True
        if key.endswith("_pem") and cur and "-----BEGIN" not in cur:
            return True
        return False

    for k, v in a1.items():
        cur = str(out.get(k) or "").strip()
        if need_fill(k, cur):
            out[k] = v
    return out
