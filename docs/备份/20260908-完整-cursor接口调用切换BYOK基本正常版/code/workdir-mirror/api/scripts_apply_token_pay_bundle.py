#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
副脑03/04：应用 Token 支付同步包（证书文件 + pay.env 合并进 api/.env）。

用法:
  cd C:\\ai24x01\\api
  python scripts_apply_token_pay_bundle.py C:\\ai24x-transfer\\token-pay-bundle.zip
  python scripts_apply_token_pay_bundle.py C:\\ai24x-transfer\\token-pay-bundle.zip --no-restart

安全:
- 只按键名 upsert，不整文件盲目覆盖无关配置
- 私钥以文件落地到 api/certs/，.env 写 PATH，清空 PEM 内联（防 ***）
- 不打印密钥内容
- 重启：优先 NSSM AI24X-core；否则尝试 pm2 core-api-8002
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
ENV_PATH = API_DIR / ".env"
CERT_DIR = API_DIR / "certs"

# 允许从 pay.env 写入的键
ALLOW_KEYS = {
    "TOKEN_PAY_ENABLED",
    "TOKEN_PAY_MOCK_ENABLED",
    "TOKEN_WECHAT_NOTIFY_URL",
    "TOKEN_ALIPAY_NOTIFY_URL",
    "TOKEN_ALIPAY_RETURN_URL",
    "WECHAT_NOTIFY_SKIP_VERIFY",
    "WECHAT_PAY_HOST",
    "WECHAT_MCH_ID",
    "WECHAT_APP_ID",
    "WECHAT_MCH_SERIAL_NO",
    "WECHAT_API_V3_KEY",
    "WECHAT_MCH_PRIVATE_KEY_PATH",
    "WECHAT_MCH_PRIVATE_KEY_PEM",
    "ALIPAY_APP_ID",
    "ALIPAY_GATEWAY",
    "ALIPAY_PUBLIC_KEY",
    "ALIPAY_MERCHANT_PRIVATE_KEY_PATH",
    "ALIPAY_MERCHANT_PRIVATE_KEY_PEM",
    "TOKEN_PAY_REUSE_A1",
}


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v
    return out


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    done: set[str] = set()
    out: list[str] = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            out.append(line)
            continue
        k = line.split("=", 1)[0].strip()
        if k in updates:
            out.append(f"{k}={updates[k]}")
            done.add(k)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in done:
            out.append(f"{k}={v}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _unpack(src: Path) -> Path:
    if src.is_dir():
        return src
    if src.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="token-pay-bundle-"))
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(tmp)
        # 若 zip 内只有一层子目录则进入
        kids = [p for p in tmp.iterdir() if p.is_dir()]
        if (tmp / "pay.env").exists():
            return tmp
        if len(kids) == 1 and (kids[0] / "pay.env").exists():
            return kids[0]
        raise SystemExit(f"zip 内找不到 pay.env: {src}")
    raise SystemExit(f"需要目录或 zip: {src}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", help="同步包目录或 zip 路径")
    ap.add_argument("--no-restart", action="store_true", help="只写配置，不 pm2 restart")
    args = ap.parse_args()

    root = _unpack(Path(args.bundle).expanduser().resolve())
    pay_env = root / "pay.env"
    wx_src = root / "certs" / "wechat_apiclient_key.pem"
    ali_src = root / "certs" / "alipay_merchant_private.pem"
    if not pay_env.exists():
        raise SystemExit(f"缺少 pay.env: {pay_env}")
    if not wx_src.exists() or not ali_src.exists():
        raise SystemExit("缺少 certs/wechat_apiclient_key.pem 或 alipay_merchant_private.pem")

    wx_text = wx_src.read_text(encoding="utf-8")
    ali_text = ali_src.read_text(encoding="utf-8")
    if "***" in wx_text or "***" in ali_text:
        raise SystemExit("证书文件含 ***，拒绝应用（请用主脑重新 export）")
    if "-----BEGIN" not in wx_text or "-----BEGIN" not in ali_text:
        raise SystemExit("证书文件缺少 PEM header")

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    wx_dst = CERT_DIR / "wechat_apiclient_key.pem"
    ali_dst = CERT_DIR / "alipay_merchant_private.pem"
    shutil.copy2(wx_src, wx_dst)
    shutil.copy2(ali_src, ali_dst)

    raw = _load_env_file(pay_env)
    updates: dict[str, str] = {}
    for k, v in raw.items():
        if k not in ALLOW_KEYS:
            continue
        if "***" in v:
            raise SystemExit(f"pay.env 中 {k} 含 ***，拒绝应用")
        updates[k] = v

    # 强制路径指向本机 certs，清空内联 PEM
    updates["WECHAT_MCH_PRIVATE_KEY_PATH"] = str(wx_dst)
    updates["WECHAT_MCH_PRIVATE_KEY_PEM"] = ""
    updates["ALIPAY_MERCHANT_PRIVATE_KEY_PATH"] = str(ali_dst)
    updates["ALIPAY_MERCHANT_PRIVATE_KEY_PEM"] = ""
    updates.setdefault("TOKEN_PAY_ENABLED", "true")
    updates["TOKEN_PAY_MOCK_ENABLED"] = "false"
    # 04 无 a1；03 有 a1 也可显式 false（凭证已写入 PATH）
    updates["TOKEN_PAY_REUSE_A1"] = "false"

    v3 = updates.get("WECHAT_API_V3_KEY", "").strip()
    if len(v3) != 32:
        raise SystemExit(f"WECHAT_API_V3_KEY 长度应为 32，当前 {len(v3)}")

    # 应用前备份 .env（防换行拼接事故）
    if ENV_PATH.exists():
        bak = ENV_PATH.with_name(
            ENV_PATH.name + ".bak." + __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
        )
        shutil.copy2(ENV_PATH, bak)
        print("OK env backup", bak)

    _upsert_env(ENV_PATH, updates)
    print("OK updated", ENV_PATH)
    print("OK certs", wx_dst, ali_dst)
    print("OK keys", ", ".join(sorted(updates.keys())))

    if not args.no_restart:
        restarted = False
        # 副脑04 / 现网：NSSM
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Restart-Service AI24X-core"],
                check=False,
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                print("OK Restart-Service AI24X-core")
                restarted = True
            else:
                print("WARN NSSM restart rc=", r.returncode, (r.stderr or r.stdout or "")[:200])
        except Exception as e:
            print("WARN NSSM restart:", e)
        if not restarted:
            try:
                subprocess.run(
                    ["pm2", "restart", "core-api-8002", "--update-env"],
                    check=False,
                )
                print("OK pm2 restart core-api-8002 --update-env")
            except FileNotFoundError:
                print("WARN: 请手动 Restart-Service AI24X-core 或 pm2 restart core-api-8002 --update-env")

    print("自检:")
    print("  curl.exe -sS http://127.0.0.1:8002/v1/billing/pay/status")
    print("  curl.exe -sS http://127.0.0.1:8002/v1/billing/plans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
