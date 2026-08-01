# -*- coding: utf-8 -*-
"""Scan user-facing web copy for ops/dev jargon. Exit 1 on hits.

Usage:
  python scripts/check_user_facing_copy.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED = [
    ("SMTP", re.compile(r"\bSMTP\b")),
    ("APP_ENV", re.compile(r"\bAPP_ENV\b")),
    ("本地预览", re.compile(r"本地预览")),
    ("正式环境", re.compile(r"正式环境")),
    ("联调", re.compile(r"联调")),
    ("副脑", re.compile(r"副脑")),
    ("上游厂商", re.compile(r"上游厂商")),
    ("挂牌", re.compile(r"挂牌")),
    ("开发包折算", re.compile(r"开发包折算")),
    ("对外统一品牌", re.compile(r"对外统一品牌")),
    ("无需记上游", re.compile(r"无需记上游")),
    ("Local preview", re.compile(r"Local preview", re.I)),
    ("upstream vendor", re.compile(r"upstream\s+vendor", re.I)),
    ("OpenRouter", re.compile(r"\bOpenRouter\b")),
    ("core-api", re.compile(r"core-api-\d+")),
]

WEB_GLOBS = [
    "web/config/locales.js",
    "web/**/*.html",
    "web/js/*.js",
]

# Internal / ops pages (not end-user product copy)
SKIP_REL = {
    "web/ai24x.html",
    "web/AI行情官.灯塔版V1.02.html",
}

SKIP_DIR_PARTS = {"ops", "archive", "bak", "vendor"}

API_GLOBS = [
    "api/*.py",
]
API_LINE_HINT = re.compile(
    r"HTTPException|detail\s*=|message\s*=|AuthEmail|\.message\s*=",
    re.I,
)


def is_comment_line(stripped: str) -> bool:
    if not stripped:
        return True
    if stripped.startswith("//") or stripped.startswith("#"):
        return True
    if stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("*/"):
        return True
    if stripped.startswith("<!--"):
        return True
    return False


def iter_web_files() -> list[Path]:
    files: list[Path] = []
    for pattern in WEB_GLOBS:
        files.extend(ROOT.glob(pattern))
    out = []
    for p in files:
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in SKIP_REL:
            continue
        if any(part in SKIP_DIR_PARTS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def iter_api_files() -> list[Path]:
    files: list[Path] = []
    for pattern in API_GLOBS:
        files.extend(ROOT.glob(pattern))
    out = []
    for p in files:
        if not p.is_file():
            continue
        if p.name.startswith("scripts_") or p.name.endswith("_test.py"):
            continue
        out.append(p)
    return sorted(out)


def scan_line(rel: str, i: int, line: str, hits: list[str]) -> None:
    stripped = line.strip()
    if is_comment_line(stripped):
        return
    for label, rx in BANNED:
        if rx.search(line):
            hits.append(f"{rel}:{i}: [{label}] {stripped[:160]}")


def main() -> int:
    hits: list[str] = []
    n = 0
    for path in iter_web_files():
        n += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for i, line in enumerate(text.splitlines(), 1):
            scan_line(rel, i, line, hits)

    for path in iter_api_files():
        n += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for i, line in enumerate(text.splitlines(), 1):
            if not API_LINE_HINT.search(line):
                continue
            scan_line(rel, i, line, hits)

    # Avoid Windows console encoding crashes
    out = getattr(sys.stdout, "buffer", None)

    def emit(s: str) -> None:
        data = (s + "\n").encode("utf-8", errors="replace")
        if out is not None:
            out.write(data)
            out.flush()
        else:
            print(s)

    if hits:
        emit("User-facing copy check FAILED (%d hit(s)):" % len(hits))
        for h in hits[:80]:
            emit("  " + h)
        if len(hits) > 80:
            emit("  ... and %d more" % (len(hits) - 80))
        return 1
    emit("User-facing copy check OK (%d files)" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
