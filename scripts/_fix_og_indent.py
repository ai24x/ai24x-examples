# -*- coding: utf-8 -*-
"""Normalize indent after og/twitter block; ensure description not flush-left."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web"

# After twitter:image line, if next non-empty line starts at col 0 with <meta|<link|<script|<style|<title
PAT = re.compile(
    r'(<meta name="twitter:image" content="https://www\.ai24x\.com/img/og-share\.png" />\n)'
    r'(<(?:meta|link|script|style|title)\b)',
    re.I,
)


def main() -> None:
    n = 0
    for p in ROOT.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        if "og:image" not in t or "twitter:image" not in t:
            continue
        t2, c = PAT.subn(r"\1  \2", t)
        # also normalize og block double-indent (4 spaces) to 2
        t2 = t2.replace("    <meta property=\"og:", "  <meta property=\"og:")
        t2 = t2.replace("    <meta name=\"twitter:", "  <meta name=\"twitter:")
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            print("fix", p.relative_to(ROOT).as_posix(), "subs", c)
            n += 1
    print("fixed", n)


if __name__ == "__main__":
    main()
