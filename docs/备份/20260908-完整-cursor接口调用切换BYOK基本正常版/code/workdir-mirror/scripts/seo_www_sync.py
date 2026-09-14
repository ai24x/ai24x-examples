#!/usr/bin/env python3
"""Sync www SEO: hreflang tags + sitemap.xml from manifest. Run from repo root."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SITEMAP = WEB / "sitemap.xml"
MANIFEST = WEB / "seo-sitemap-urls.txt"
HREFLANG_BLOCK = """  <link rel="alternate" hreflang="en" href="{url}" />
  <link rel="alternate" hreflang="zh-CN" href="{url}" />
  <link rel="alternate" hreflang="x-default" href="{url}" />"""

GLOB_DIRS = ["", "blog", "guides", "models"]


def collect_html_files() -> list[Path]:
    out: list[Path] = []
    for sub in GLOB_DIRS:
        d = WEB / sub if sub else WEB
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.html")):
            name = p.name.lower()
            if name in (
                "token-admin.html",
                "command-center.html",
                "demo.html",
                "paypal.html",
                "dashboard.html",
                "account.html",
                "ai24x.html",
            ):
                continue
            if name.startswith("ai行情官"):
                continue
            out.append(p)
    return out


def canonical_url(text: str) -> str | None:
    m = re.search(
        r'<link\s+rel="canonical"\s+href="(https://www\.ai24x\.com[^"]*)"',
        text,
        re.I,
    )
    return m.group(1).rstrip("/") if m else None


def patch_hreflang(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "hreflang=" in text:
        return False
    url = canonical_url(text)
    if not url:
        return False
    if not url.endswith(".html") and not url.endswith(".ai24x.com"):
        url = url + "/"
    block = HREFLANG_BLOCK.format(url=url)
    if '<link rel="canonical"' in text:
        text2 = re.sub(
            r'(<link rel="canonical" href="[^"]+"\s*/>\s*)',
            r"\1" + block + "\n",
            text,
            count=1,
            flags=re.I,
        )
    else:
        return False
    if text2 == text:
        return False
    path.write_text(text2, encoding="utf-8", newline="\n")
    return True


def build_sitemap() -> None:
    lines = [
        p.strip()
        for p in MANIFEST.read_text(encoding="utf-8").splitlines()
        if p.strip() and not p.strip().startswith("#")
    ]
    lastmod = "2026-08-28"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc in lines:
        if not loc.startswith("https://"):
            loc = "https://www.ai24x.com/" + loc.lstrip("/")
        pri = "0.5"
        freq = "monthly"
        if loc.rstrip("/").endswith("ai24x.com") or loc.endswith("ai24x.com/"):
            pri, freq = "1.0", "daily"
        elif "/blog/what-is-ai-gateway" in loc:
            pri, freq = "0.9", "monthly"
        elif "/blog/" in loc:
            pri, freq = "0.85", "monthly"
        elif loc.endswith("/pricing.html") or loc.endswith("/product.html"):
            pri, freq = "0.9", "weekly"
        elif "/guides/" in loc or "/models/" in loc:
            pri, freq = "0.7", "monthly"
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append(f"    <changefreq>{freq}</changefreq>")
        parts.append(f"    <priority>{pri}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")
    SITEMAP.write_text("\n".join(parts), encoding="utf-8", newline="\n")


def main() -> None:
    n = 0
    for p in collect_html_files():
        if patch_hreflang(p):
            n += 1
            print("hreflang:", p.relative_to(ROOT))
    build_sitemap()
    n_urls = len(
        [
            l
            for l in MANIFEST.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
    )
    print("sitemap:", SITEMAP.relative_to(ROOT), "urls", n_urls)
    print("hreflang patched:", n)


if __name__ == "__main__":
    main()
