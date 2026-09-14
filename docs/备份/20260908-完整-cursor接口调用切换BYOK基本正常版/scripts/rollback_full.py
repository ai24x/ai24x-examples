#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整回滚：数据库 + 可选代码（git archive / workdir-mirror / secrets）。默认干跑。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
import re

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = Path(__file__).resolve().parents[1]


def _pg_bin(name: str) -> str:
    candidates = [
        Path(rf"C:\AI24X\postgresql\pgsql\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\16\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\15\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\14\bin") / f"{name}.exe",
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    raise FileNotFoundError(name)


def _parse_pg_url(url: str) -> dict:
    raw = re.sub(r"^postgresql\+\w+", "postgresql", url.strip(), flags=re.I)
    u = urlparse(raw)
    return {
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "host": u.hostname or "127.0.0.1",
        "port": str(u.port or 5432),
        "database": (u.path or "/").lstrip("/").split("?")[0],
    }


def _load_manifest() -> dict:
    p = BUNDLE / "manifest.json"
    if not p.is_file():
        raise SystemExit(f"missing {p} — run backup_full.py first")
    return json.loads(p.read_text(encoding="utf-8"))


def restore_db(apply: bool) -> None:
    man = _load_manifest()
    pg_restore = _pg_bin("pg_restore")
    # Prefer live .env to target current host; dump filename is dbname.dump
    for row in man.get("databases") or []:
        if not row.get("ok"):
            continue
        dump_rel = row["dump"]
        dump = BUNDLE / dump_rel
        dbname = row["database"]
        env_rel = row.get("source_env") or ""
        env_path = ROOT / env_rel.replace("/", os.sep)
        if not env_path.is_file():
            print("SKIP no env", env_path)
            continue
        url = None
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(row.get("source_key") or "DATABASE_URL"):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        if not url:
            print("SKIP no url in", env_path)
            continue
        info = _parse_pg_url(url)
        cmd = [
            pg_restore,
            "-h",
            info["host"],
            "-p",
            info["port"],
            "-U",
            info["user"],
            "-d",
            info["database"],
            "--clean",
            "--if-exists",
            str(dump),
        ]
        print(("APPLY " if apply else "[dry] "), " ".join(cmd))
        if apply:
            env = os.environ.copy()
            if info["password"]:
                env["PGPASSWORD"] = info["password"]
            r = subprocess.run(cmd, env=env)
            print("exit", r.returncode, "db=", dbname)


def restore_code_archive(apply: bool) -> None:
    z = BUNDLE / "code" / "repo-HEAD.zip"
    if not z.is_file():
        raise SystemExit(f"missing {z}")
    print(("APPLY " if apply else "[dry] "), "extract", z, "->", ROOT)
    if not apply:
        return
    # extract over repo (does not delete new untracked files)
    subprocess.run(
        ["tar", "-xf", str(z), "-C", str(ROOT)],
        check=False,
    )
    # Windows may lack tar zip support the same way — use PowerShell Expand-Archive to temp then copy
    tmp = BUNDLE / "_restore_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Expand-Archive -LiteralPath '{z}' -DestinationPath '{tmp}' -Force",
        ],
        check=True,
    )
    for src in tmp.rglob("*"):
        if src.is_file():
            rel = src.relative_to(tmp)
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    shutil.rmtree(tmp, ignore_errors=True)
    print("code archive restored")


def restore_secrets(apply: bool) -> None:
    sec = BUNDLE / "secrets"
    if not sec.is_dir():
        return
    for bak in sec.glob("*.bak"):
        # api__.env.bak style -> api/.env
        name = bak.name[: -len(".bak")]
        rel = name.replace("__", os.sep)
        # fix double: api__.env -> wait, we used replace / with __ so api/.env -> api__.env
        # Actually: "api\\.env".replace("\\","__") -> "api__.env" — broken for .env
        # Our saver used: str(relative).replace("\\","__").replace("/","__")
        # so api\.env -> api__.env  (dot preserved)
        dst = ROOT / rel
        # if path looks wrong (api__.env as single file name), map known patterns
        if not dst.parent.exists() and "__" in name:
            # re-parse: last component may be .env
            parts = name.split("__")
            dst = ROOT.joinpath(*parts)
        print(("APPLY " if apply else "[dry] "), bak.name, "->", dst)
        if apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bak, dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db-only", action="store_true")
    ap.add_argument("--code-only", action="store_true")
    ap.add_argument("--secrets", action="store_true", help="also restore .env from secrets/")
    args = ap.parse_args()
    man = _load_manifest()
    print("label=", man.get("label"), "git=", (man.get("code") or {}).get("git_short"))
    if args.code_only:
        restore_code_archive(args.apply)
    elif args.db_only:
        restore_db(args.apply)
    else:
        restore_db(args.apply)
        restore_code_archive(args.apply)
    if args.secrets:
        restore_secrets(args.apply)
    if not args.apply:
        print("Pass --apply to execute. Optional: --db-only / --code-only / --secrets")
    else:
        print("Done. Restart services: AI24X-core / AI24X-open-api / AI24X-markets-api as needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
