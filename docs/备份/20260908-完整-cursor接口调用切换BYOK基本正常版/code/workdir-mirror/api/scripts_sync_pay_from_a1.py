#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 a1 admin_config 同步商户凭证到主站 api/.env（只写凭证，绝不复制 a1 notify）。

用法（仓库根目录）:
  python api/scripts_sync_pay_from_a1.py

安全:
- 不打印密钥内容
- 不修改 p/a1 任何文件
- TOKEN_*_NOTIFY_URL 保持独立（默认 api.ai24x.com Token 路径）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A1_SERVER = ROOT.parent / "p" / "a1" / "api" / "server"
if not A1_SERVER.exists():
    # script lives in api/
    ROOT = Path(__file__).resolve().parents[1]
    A1_SERVER = ROOT.parent / "p" / "a1" / "api" / "server" if (ROOT.name == "api") else ROOT / "p" / "a1" / "api" / "server"

# normalize: this file is api/scripts_sync_pay_from_a1.py
API_DIR = Path(__file__).resolve().parent
REPO = API_DIR.parent
A1_SERVER = REPO / "p" / "a1" / "api" / "server"
ENV_PATH = API_DIR / ".env"

# a1 admin_config key -> api/.env key
MAP = {
    "wechat_mch_id": "WECHAT_MCH_ID",
    "wechat_app_id": "WECHAT_APP_ID",
    "wechat_mch_serial_no": "WECHAT_MCH_SERIAL_NO",
    "wechat_mch_private_key_path": "WECHAT_MCH_PRIVATE_KEY_PATH",
    "wechat_api_v3_key": "WECHAT_API_V3_KEY",
    "wechat_pay_host": "WECHAT_PAY_HOST",
    # PEM 若 path 为空可作后备
    "wechat_mch_private_key_pem": "WECHAT_MCH_PRIVATE_KEY_PEM",
    "alipay_app_id": "ALIPAY_APP_ID",
    "alipay_gateway": "ALIPAY_GATEWAY",
    "alipay_merchant_private_key_path": "ALIPAY_MERCHANT_PRIVATE_KEY_PATH",
    "alipay_merchant_private_key_pem": "ALIPAY_MERCHANT_PRIVATE_KEY_PEM",
    "alipay_public_key": "ALIPAY_PUBLIC_KEY",
}

# 绝不从 a1 复制这些
FORBIDDEN_A1 = {
    "wechat_notify_url",
    "alipay_notify_url",
    "alipay_return_url",
}

TOKEN_DEFAULTS = {
    "TOKEN_PAY_ENABLED": "false",
    "TOKEN_PAY_MOCK_ENABLED": "true",
    "TOKEN_WECHAT_NOTIFY_URL": "https://api.ai24x.com/v1/billing/wechat/notify",
    "TOKEN_ALIPAY_NOTIFY_URL": "https://api.ai24x.com/v1/billing/alipay/notify",
    "TOKEN_ALIPAY_RETURN_URL": "https://www.ai24x.com/console.html",
    "WECHAT_NOTIFY_SKIP_VERIFY": "false",
}


def _load_a1_config() -> dict[str, str]:
    sys.path.insert(0, str(A1_SERVER))
    import os

    os.chdir(str(A1_SERVER))
    from app import db  # type: ignore

    return dict(db.admin_config_get_all() or {})


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    keys_done = set()
    out: list[str] = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            out.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in updates:
            v = updates[k]
            # multiline PEM: keep as single line with \n escaped? Better use triple - env usually single line
            # For PEM with newlines, write as literal with \n replaced - pydantic/settings may need real newlines
            # Store PEM with actual newlines using quotes? Standard .env often uses """ 
            out.append(f"{k}={v}")
            keys_done.add(k)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in keys_done:
            out.append(f"{k}={v}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _env_escape(v: str) -> str:
    """把多行 PEM 收成单行，用 \\n 表示换行，读取时再还原。"""
    if "\n" in v or "\r" in v:
        return v.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    return v


def main() -> int:
    if not A1_SERVER.exists():
        print("a1 server path missing:", A1_SERVER)
        return 1
    cfg = _load_a1_config()
    updates: dict[str, str] = dict(TOKEN_DEFAULTS)
    synced = []
    for a1k, envk in MAP.items():
        if a1k in FORBIDDEN_A1:
            continue
        raw = (cfg.get(a1k) or "").strip()
        if not raw:
            continue
        # 私钥路径：若相对 a1，尽量转成绝对路径
        if a1k.endswith("_path") and raw and not Path(raw).is_absolute():
            cand = (A1_SERVER / raw).resolve()
            if cand.exists():
                raw = str(cand)
            else:
                cand2 = (A1_SERVER / "app" / raw).resolve()
                if cand2.exists():
                    raw = str(cand2)
        updates[envk] = _env_escape(raw)
        synced.append(envk)

    # 确保不写入 a1 notify
    for bad in ("WECHAT_NOTIFY_URL", "ALIPAY_NOTIFY_URL"):
        updates.pop(bad, None)

    _upsert_env(ENV_PATH, updates)
    print("wrote", ENV_PATH)
    print("synced_keys", sorted(synced))
    print("token_notify_kept", TOKEN_DEFAULTS["TOKEN_WECHAT_NOTIFY_URL"])
    print("TOKEN_PAY_ENABLED still false — enable only after small live test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
