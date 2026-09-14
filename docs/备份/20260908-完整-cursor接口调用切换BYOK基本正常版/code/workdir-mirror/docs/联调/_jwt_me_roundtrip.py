"""副脑03：JWT 文件对齐 + 本地 /api/me 闭环（不打印密钥原文）。"""
from __future__ import annotations

import hashlib
import os
import urllib.error
import urllib.request
from pathlib import Path


def load(path: str, name: str) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith(name + "="):
            v = s.split("=", 1)[1].strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            return v
    return ""


def meta(v: str) -> dict:
    v = v or ""
    h = hashlib.sha256(v.encode()).hexdigest()[:12]
    return {
        "len": len(v),
        "tail": ("***" + v[-4:]) if len(v) >= 4 else repr(v),
        "sha12": h,
        "empty": not bool(v),
    }


def main() -> None:
    core_env = os.environ.get("CORE_ENV", r"C:\ai24x01\api\.env")
    a1_env = os.environ.get("A1_ENV", r"C:\ai24x01\p\a1\api\server\.env")
    a1_me = os.environ.get("A1_ME", "http://127.0.0.1:8001/api/me")

    print("core_env", core_env, "exists", Path(core_env).is_file())
    print("a1_env", a1_env, "exists", Path(a1_env).is_file())

    sk = load(core_env, "SECRET_KEY")
    jk = load(a1_env, "AI24X_JWT_SECRET")
    base = load(a1_env, "AI24X_IDENTITY_API_BASE")
    print("SECRET_KEY", meta(sk))
    print("AI24X_JWT_SECRET", meta(jk))
    print("FILE_MATCH", sk == jk)
    print("IDENTITY_API_BASE", base or "(empty)")

    from jose import jwt

    token = jwt.encode(
        {"sub": "1", "email": "", "phone": "", "iat": 1, "exp": 9999999999},
        sk,
        algorithm="HS256",
    )
    if isinstance(token, bytes):
        token = token.decode()
    try:
        jwt.decode(token, jk, algorithms=["HS256"])
        print("JOSE_CROSS_DECODE", "OK")
    except Exception as e:
        print("JOSE_CROSS_DECODE", "FAIL", type(e).__name__, str(e)[:120])

    req = urllib.request.Request(a1_me, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print("LOCAL_ME", r.status, r.read()[:160])
    except urllib.error.HTTPError as e:
        print("LOCAL_ME", e.code, e.read()[:200])
    except Exception as e:
        print("LOCAL_ME", "ERR", e)


if __name__ == "__main__":
    main()
