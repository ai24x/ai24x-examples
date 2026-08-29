#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整备份：整仓代码 + 各子项目 PostgreSQL（支持回滚）。不含将 dump/密钥提交进 git。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[4]
BUNDLE = Path(__file__).resolve().parents[1]
LABEL = "完整-国际双支付ok1.01"

ENV_CANDIDATES = [
    ROOT / "api" / ".env",
    ROOT / "p" / "open" / "api" / ".env",
    ROOT / "p" / "markets" / "api" / "server" / ".env",
    ROOT / "p" / "a1" / "api" / "server" / ".env",
    ROOT / "p" / "game" / "fisher" / "api" / "server" / ".env",
]

ENV_KEYS = (
    "DATABASE_URL",
    "AI24X_DATABASE_URL",
    "FISHER_DATABASE_URL",
)


def _pg_bin(name: str) -> str:
    candidates = [
        Path(rf"C:\AI24X\postgresql\pgsql\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\16\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\15\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\14\bin") / f"{name}.exe",
        Path(rf"C:\Program Files\PostgreSQL\13\bin") / f"{name}.exe",
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    which = shutil.which(name) or shutil.which(f"{name}.exe")
    if which:
        return which
    raise FileNotFoundError(f"{name} not found")


def _read_env_urls(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    out: list[tuple[str, str]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k not in ENV_KEYS:
            continue
        v = v.strip().strip('"').strip("'")
        if v:
            out.append((k, v))
    return out


def _parse_pg_url(url: str) -> dict:
    # sqlalchemy may use postgresql+psycopg2://
    raw = re.sub(r"^postgresql\+\w+", "postgresql", url.strip(), flags=re.I)
    u = urlparse(raw)
    if u.scheme not in ("postgresql", "postgres"):
        raise ValueError(f"not postgres: {url[:32]}...")
    return {
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "host": u.hostname or "127.0.0.1",
        "port": str(u.port or 5432),
        "database": (u.path or "/").lstrip("/").split("?")[0],
    }


def _git(*args: str) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (r.stdout or "").strip()


def backup_code(code_dir: Path) -> dict:
    code_dir.mkdir(parents=True, exist_ok=True)
    head = _git("rev-parse", "HEAD")
    short = _git("rev-parse", "--short=12", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")

    bundle = code_dir / "repo.bundle"
    archive = code_dir / "repo-HEAD.zip"
    print("git bundle ->", bundle)
    subprocess.run(
        ["git", "bundle", "create", str(bundle), "--all"],
        cwd=str(ROOT),
        check=True,
    )
    print("git archive ->", archive)
    with open(archive, "wb") as f:
        subprocess.run(
            ["git", "archive", "--format=zip", "HEAD"],
            cwd=str(ROOT),
            check=True,
            stdout=f,
        )

    # working-tree extras not always in git (override json, etc.) — full tree mirror without secrets/heavy junk
    mirror = code_dir / "workdir-mirror"
    if mirror.exists():
        shutil.rmtree(mirror)
    mirror.mkdir(parents=True)
    exclude_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".cursor",
        "agent-transcripts",
        "terminals",
        ".pytest_cache",
        "dist",
        "build",
        "_chrome_profile",
        "_chrome_profile5",
        ".chrome_tmp",
        ".chrome_tmp2",
        ".chrome_tmp3",
        ".chrome_tmp4",
        ".chrome_tmpA",
        ".chrome_tmpB",
        ".chrome_tmpC",
        ".chrome_tmpD",
        ".chrome_tmpE",
        ".chrome_tmpG",
        ".chrome_tmpH",
        "Cache",
        "Code Cache",
        "GPUCache",
        "component_crx_cache",
        "WasmTtsEngine",
    }
    exclude_suffix = {".pyc", ".pyo", ".dump", ".zip", ".bundle", ".log", ".mp4", ".webm"}
    copied = 0
    for src_root, dirs, files in os.walk(ROOT):
        rel_root = Path(src_root).relative_to(ROOT)
        dirs[:] = [
            d
            for d in dirs
            if d not in exclude_dirs
            and not d.startswith(".bak")
            and not d.startswith(".chrome_tmp")
            and not d.startswith("_chrome")
        ]
        # skip all snapshot/backup trees (avoid nesting)
        if "备份" in rel_root.parts:
            dirs[:] = []
            continue
        # skip ops logs / large runtime noise
        if len(rel_root.parts) >= 1 and rel_root.parts[0] == "ops":
            files = [f for f in files if not f.endswith(".log")]
        for name in files:
            if Path(name).suffix.lower() in exclude_suffix:
                continue
            if name.endswith(".log") or "_uvicorn_" in name:
                continue
            if name in (".env",) or name.endswith(".env") or name.startswith(".env."):
                continue  # secrets handled separately
            src = Path(src_root) / name
            # skip absurdly large files (>50MB)
            try:
                if src.stat().st_size > 50 * 1024 * 1024:
                    continue
            except OSError:
                continue
            dst = mirror / rel_root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                print("skip", src, e)
    return {
        "git_head": head,
        "git_short": short,
        "branch": branch,
        "repo_bundle": "code/repo.bundle",
        "repo_archive_zip": "code/repo-HEAD.zip",
        "workdir_mirror_files": copied,
        "workdir_mirror": "code/workdir-mirror",
    }


def backup_secrets(sec_dir: Path) -> list[str]:
    sec_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for p in ENV_CANDIDATES:
        if not p.is_file():
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "__").replace("/", "__")
        dst = sec_dir / f"{rel}.bak"
        shutil.copy2(p, dst)
        saved.append(str(dst.relative_to(BUNDLE)).replace("\\", "/"))
    note = sec_dir / "README.txt"
    note.write_text(
        "含 .env 备份，勿提交 git、勿外传。回滚时按路径名还原到仓库对应位置。\n",
        encoding="utf-8",
    )
    return saved


def backup_databases(db_dir: Path) -> list[dict]:
    db_dir.mkdir(parents=True, exist_ok=True)
    pg_dump = _pg_bin("pg_dump")
    seen: set[str] = set()
    results: list[dict] = []
    for env_path in ENV_CANDIDATES:
        for key, url in _read_env_urls(env_path):
            try:
                info = _parse_pg_url(url)
            except Exception as e:
                results.append({"ok": False, "env": str(env_path), "key": key, "error": str(e)})
                continue
            dbname = info["database"]
            if not dbname or dbname in seen:
                continue
            seen.add(dbname)
            out = db_dir / f"{dbname}.dump"
            env = os.environ.copy()
            if info["password"]:
                env["PGPASSWORD"] = info["password"]
            cmd = [
                pg_dump,
                "-h",
                info["host"],
                "-p",
                info["port"],
                "-U",
                info["user"],
                "-d",
                dbname,
                "-Fc",
                "-f",
                str(out),
            ]
            print("RUN", " ".join(cmd[:10]), "...")
            try:
                subprocess.run(cmd, check=True, env=env)
                results.append(
                    {
                        "ok": True,
                        "database": dbname,
                        "host": info["host"],
                        "source_env": str(env_path.relative_to(ROOT)).replace("\\", "/"),
                        "source_key": key,
                        "dump": f"db/{dbname}.dump",
                        "bytes": out.stat().st_size if out.is_file() else 0,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "ok": False,
                        "database": dbname,
                        "host": info["host"],
                        "source_env": str(env_path.relative_to(ROOT)).replace("\\", "/"),
                        "error": str(e),
                    }
                )
    return results


def backup_markets_site() -> dict | None:
    site = Path(r"C:\sites\markets.ai24x.com")
    if not site.is_dir():
        return None
    dest = BUNDLE / "sites" / "markets.ai24x.com"
    if dest.exists():
        shutil.rmtree(dest)
    print("robocopy markets site ->", dest)
    # use robocopy on Windows
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [
            "robocopy",
            str(site),
            str(dest),
            "/E",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS",
            "/NP",
        ],
        capture_output=True,
        text=True,
    )
    # robocopy <8 = success
    ok = r.returncode < 8
    return {
        "ok": ok,
        "source": str(site),
        "dest": "sites/markets.ai24x.com",
        "robocopy_code": r.returncode,
    }


def main() -> int:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    code_meta = backup_code(BUNDLE / "code")
    secrets = backup_secrets(BUNDLE / "secrets")
    dbs = backup_databases(BUNDLE / "db")
    markets = backup_markets_site()

    manifest = {
        "label": LABEL,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repo_root": str(ROOT),
        "code": code_meta,
        "secrets": secrets,
        "databases": dbs,
        "markets_site": markets,
    }
    (BUNDLE / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    db_ok = all(x.get("ok") for x in dbs) if dbs else False
    print("OK", LABEL, "dbs=", len(dbs), "db_ok=", db_ok, "secrets=", len(secrets))
    print(json.dumps(manifest, ensure_ascii=False, indent=2)[:2000])
    if not dbs:
        print("WARN: no databases dumped", file=sys.stderr)
        return 2
    if not db_ok:
        print("WARN: some database dumps failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
