#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从本机已跑通的 api/.env + 微信私钥文件，导出「Token 支付同步包」。

- 不写入 git（默认输出到 E:/AI24X/bak/…）
- 私钥以独立 .pem 文件携带，避免聊天/Cursor 把 PEM 打成 ***
- 副脑03 用 scripts_apply_token_pay_bundle.py 一键合并进生产 .env 并重启

用法（仓库根或 api 目录）:
  python api/scripts_export_token_pay_bundle.py
  python api/scripts_export_token_pay_bundle.py --out E:/AI24X/bak/token-pay-bundle
"""
from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
REPO = API_DIR.parent
LOCAL_ENV = API_DIR / ".env"
LOCAL_WX_PEM = REPO / "p" / "a1" / "api" / "server" / "apiclient_key.pem"

# 同步到副脑03 的键（不含 a1 notify）
EXPORT_KEYS = [
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
    "ALIPAY_APP_ID",
    "ALIPAY_GATEWAY",
    "ALIPAY_PUBLIC_KEY",
]

DEFAULTS = {
    "TOKEN_PAY_ENABLED": "true",
    "TOKEN_PAY_MOCK_ENABLED": "false",
    "TOKEN_WECHAT_NOTIFY_URL": "https://api.ai24x.com/v1/billing/wechat/notify",
    "TOKEN_ALIPAY_NOTIFY_URL": "https://api.ai24x.com/v1/billing/alipay/notify",
    "TOKEN_ALIPAY_RETURN_URL": "https://www.ai24x.com/console.html",
    "WECHAT_NOTIFY_SKIP_VERIFY": "false",
    "WECHAT_PAY_HOST": "https://api.mch.weixin.qq.com",
}

# 副脑03 落地后的证书绝对路径（APPLY 会按此写入 .env）
SB03_CERT_DIR = r"C:\ai24x01\api\certs"
SB03_WX_PATH = SB03_CERT_DIR + r"\wechat_apiclient_key.pem"
SB03_ALI_PATH = SB03_CERT_DIR + r"\alipay_merchant_private.pem"


def _load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v
    return out


def _unescape_pem(raw: str) -> str:
    s = (raw or "").strip().strip('"').strip("'")
    if "\\n" in s and "-----BEGIN" in s and "\n" not in s:
        s = s.replace("\\n", "\n")
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    # 修复误写成双 BEGIN 的公钥尾
    if s.count("-----BEGIN PUBLIC KEY-----") >= 2 and "-----END PUBLIC KEY-----" not in s:
        parts = s.rsplit("-----BEGIN PUBLIC KEY-----", 1)
        s = parts[0].rstrip() + "\n-----END PUBLIC KEY-----"
    return s


def _must_pem(text: str, label: str) -> str:
    t = _unescape_pem(text)
    if "***" in t or not t:
        raise SystemExit(f"{label}: 空或为 *** 占位，拒绝导出")
    if "-----BEGIN" not in t or "-----END" not in t:
        raise SystemExit(f"{label}: 缺少 PEM header/footer")
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="",
        help="输出目录（默认 E:/AI24X/bak/token-pay-bundle-时间戳）",
    )
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out) if args.out else Path(r"E:/AI24X/bak") / f"token-pay-bundle-{stamp}"
    cert_dir = out_dir / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)

    env = _load_env(LOCAL_ENV)

    # 微信私钥：优先本地 pem 文件，否则 .env 内联
    if LOCAL_WX_PEM.exists():
        wx_pem = _must_pem(LOCAL_WX_PEM.read_text(encoding="utf-8"), "wechat pem file")
    else:
        wx_pem = _must_pem(env.get("WECHAT_MCH_PRIVATE_KEY_PEM", ""), "WECHAT_MCH_PRIVATE_KEY_PEM")
    (cert_dir / "wechat_apiclient_key.pem").write_text(wx_pem + "\n", encoding="utf-8")

    ali_pem = _must_pem(env.get("ALIPAY_MERCHANT_PRIVATE_KEY_PEM", ""), "ALIPAY_MERCHANT_PRIVATE_KEY_PEM")
    (cert_dir / "alipay_merchant_private.pem").write_text(ali_pem + "\n", encoding="utf-8")

    # 公钥也落文件，.env 用 PATH 思路：仍写 ALIPAY_PUBLIC_KEY 单行（较短）
    ali_pub = _unescape_pem(env.get("ALIPAY_PUBLIC_KEY", ""))
    if ali_pub and "***" not in ali_pub:
        if ali_pub.count("-----BEGIN PUBLIC KEY-----") >= 2 and "-----END PUBLIC KEY-----" not in ali_pub:
            ali_pub = ali_pub.rsplit("-----BEGIN PUBLIC KEY-----", 1)[0].rstrip() + "\n-----END PUBLIC KEY-----"
        (cert_dir / "alipay_public.pem").write_text(ali_pub + "\n", encoding="utf-8")

    lines = [
        "# Token pay bundle — APPLY 会合并进 C:\\ai24x01\\api\\.env",
        "# 私钥走文件路径，避免 PEM 内联被打成 ***",
        f"TOKEN_PAY_ENABLED={env.get('TOKEN_PAY_ENABLED', DEFAULTS['TOKEN_PAY_ENABLED'])}",
        f"TOKEN_PAY_MOCK_ENABLED={env.get('TOKEN_PAY_MOCK_ENABLED', DEFAULTS['TOKEN_PAY_MOCK_ENABLED']) or DEFAULTS['TOKEN_PAY_MOCK_ENABLED']}",
        # 生产实付强制 false（本机若开了 mock，导出时仍建议关）
        "TOKEN_PAY_MOCK_ENABLED=false",
        f"TOKEN_WECHAT_NOTIFY_URL={env.get('TOKEN_WECHAT_NOTIFY_URL') or DEFAULTS['TOKEN_WECHAT_NOTIFY_URL']}",
        f"TOKEN_ALIPAY_NOTIFY_URL={env.get('TOKEN_ALIPAY_NOTIFY_URL') or DEFAULTS['TOKEN_ALIPAY_NOTIFY_URL']}",
        f"TOKEN_ALIPAY_RETURN_URL={env.get('TOKEN_ALIPAY_RETURN_URL') or DEFAULTS['TOKEN_ALIPAY_RETURN_URL']}",
        f"WECHAT_NOTIFY_SKIP_VERIFY={env.get('WECHAT_NOTIFY_SKIP_VERIFY') or DEFAULTS['WECHAT_NOTIFY_SKIP_VERIFY']}",
        f"WECHAT_PAY_HOST={env.get('WECHAT_PAY_HOST') or DEFAULTS['WECHAT_PAY_HOST']}",
        f"WECHAT_MCH_ID={env.get('WECHAT_MCH_ID', '').strip()}",
        f"WECHAT_APP_ID={env.get('WECHAT_APP_ID', '').strip()}",
        f"WECHAT_MCH_SERIAL_NO={env.get('WECHAT_MCH_SERIAL_NO', '').strip()}",
        f"WECHAT_API_V3_KEY={env.get('WECHAT_API_V3_KEY', '').strip()}",
        f"WECHAT_MCH_PRIVATE_KEY_PATH={SB03_WX_PATH}",
        "WECHAT_MCH_PRIVATE_KEY_PEM=",
        f"ALIPAY_APP_ID={env.get('ALIPAY_APP_ID', '').strip()}",
        f"ALIPAY_GATEWAY={env.get('ALIPAY_GATEWAY') or 'https://openapi.alipay.com/gateway.do'}",
        f"ALIPAY_MERCHANT_PRIVATE_KEY_PATH={SB03_ALI_PATH}",
        "ALIPAY_MERCHANT_PRIVATE_KEY_PEM=",
    ]
    # 公钥较短：单行 \n
    if ali_pub and "***" not in ali_pub:
        pub_one = ali_pub.replace("\n", "\\n")
        lines.append(f"ALIPAY_PUBLIC_KEY={pub_one}")
    else:
        raise SystemExit("ALIPAY_PUBLIC_KEY missing")

    for k in ("WECHAT_MCH_ID", "WECHAT_APP_ID", "WECHAT_MCH_SERIAL_NO", "WECHAT_API_V3_KEY", "ALIPAY_APP_ID"):
        if not env.get(k, "").strip():
            raise SystemExit(f"本地 .env 缺少 {k}")

    v3 = env.get("WECHAT_API_V3_KEY", "").strip().strip('"').strip("'")
    if len(v3) != 32:
        raise SystemExit(f"WECHAT_API_V3_KEY 长度应为 32，当前 {len(v3)}")

    pay_env = out_dir / "pay.env"
    # 去重 TOKEN_PAY_MOCK（上面写了两次，保留 false）
    cleaned: list[str] = []
    seen_mock = False
    for line in lines:
        if line.startswith("TOKEN_PAY_MOCK_ENABLED="):
            if seen_mock:
                continue
            seen_mock = True
            cleaned.append("TOKEN_PAY_MOCK_ENABLED=false")
        else:
            cleaned.append(line)
    pay_env.write_text("\n".join(cleaned) + "\n", encoding="utf-8")

    readme = out_dir / "README.txt"
    readme.write_text(
        "\n".join(
            [
                "AI24X Token 支付同步包（含商户密钥文件，勿提交 git / 勿贴公开群）",
                f"生成时间: {stamp}",
                "",
                "副脑03:",
                "1) 把本目录整个拷到服务器，例如 C:\\ai24x-transfer\\token-pay-bundle\\",
                "2) 先更新代码: cd C:\\ai24x01 && git pull origin master",
                "3) 应用:",
                "   cd C:\\ai24x01\\api",
                "   python scripts_apply_token_pay_bundle.py C:\\ai24x-transfer\\token-pay-bundle",
                "4) 回传: curl.exe -sS http://127.0.0.1:8002/v1/billing/plans",
                "",
            ]
        ),
        encoding="utf-8",
    )

    zip_path = out_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in out_dir.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=str(p.relative_to(out_dir)))

    print("OK bundle dir:", out_dir)
    print("OK zip:", zip_path)
    print("wx pem bytes:", (cert_dir / "wechat_apiclient_key.pem").stat().st_size)
    print("ali pem bytes:", (cert_dir / "alipay_merchant_private.pem").stat().st_size)
    print("下一步: 把 zip 拷到副脑03，git pull 后运行 scripts_apply_token_pay_bundle.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
