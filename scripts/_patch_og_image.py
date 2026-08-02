# -*- coding: utf-8 -*-
"""Add og:image (+ basic OG) to public pages that have canonical but lack og:image."""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web"
OG_IMG = "https://www.ai24x.com/img/og-share.png"
SKIP_NAMES = {
    "token-admin.html",
    "command-center.html",
    "ai24x.html",
    "demo.html",
    "dashboard.html",
    "account.html",
    "404.html",
    "console.html",
    "paypal.html",
    "partner.html",
}


def extract(tag: str, text: str) -> str:
    m = re.search(tag, text, flags=re.I | re.S)
    return (m.group(1).strip() if m else "") or ""


def main() -> None:
    n = 0
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT).as_posix()
        if p.name in SKIP_NAMES or "AI" in p.name and "行情" in p.name:
            continue
        t = p.read_text(encoding="utf-8")
        if 'property="og:image"' in t or "property='og:image'" in t:
            continue
        if 'rel="canonical"' not in t:
            continue

        title = extract(r"<title>([^<]+)</title>", t)
        desc = extract(
            r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
            t,
        )
        canon = extract(
            r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']',
            t,
        )
        if not canon:
            continue
        if not title:
            title = "AI24X"
        if not desc:
            desc = "China LLM API · OpenAI-compatible · PayPal USD · AI24X"

        # Escape for attribute context (title/desc may contain &)
        title_a = html.escape(title, quote=True)
        desc_a = html.escape(desc, quote=True)
        block = (
            f'  <meta property="og:type" content="website" />\n'
            f'  <meta property="og:title" content="{title_a}" />\n'
            f'  <meta property="og:description" content="{desc_a}" />\n'
            f'  <meta property="og:url" content="{canon}" />\n'
            f'  <meta property="og:image" content="{OG_IMG}" />\n'
            f'  <meta property="og:image:width" content="1200" />\n'
            f'  <meta property="og:image:height" content="630" />\n'
            f'  <meta name="twitter:card" content="summary_large_image" />\n'
            f'  <meta name="twitter:image" content="{OG_IMG}" />\n'
        )

        # Insert after canonical link
        pat = re.compile(
            r'(<link\s+rel=["\']canonical["\']\s+href=["\'][^"\']+["\']\s*/?>)',
            re.I,
        )
        m = pat.search(t)
        if not m:
            print("no-canon-match", rel)
            continue
        # Keep following whitespace/indent of next tag intact
        t2 = t[: m.end()] + "\n" + block + t[m.end() :]
        p.write_text(t2, encoding="utf-8")
        print("ok", rel)
        n += 1
    print("patched", n)


if __name__ == "__main__":
    main()
