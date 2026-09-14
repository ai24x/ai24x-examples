# -*- coding: utf-8 -*-
"""Generate web/sitemap.xml for www.ai24x.com public pages."""
from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web"
BASE = "https://www.ai24x.com"
TODAY = date.today().isoformat()

# Do not include Disallow pages from robots.txt
EXCLUDE = {
    "token-admin.html",
    "console.html",
    "account.html",
    "ai24x.html",
    "command-center.html",
    "demo.html",
    "paypal.html",
    "dashboard.html",
    "404.html",
    "partner.html",  # optional internal; skip if ops-ish
}

# Explicit include order (public SEO set)
PAGES = [
    ("index.html", "weekly", "1.0"),
    ("pricing.html", "weekly", "0.9"),
    ("product.html", "weekly", "0.8"),
    ("docs.html", "weekly", "0.8"),
    ("help.html", "weekly", "0.7"),
    ("refer.html", "weekly", "0.7"),
    ("register.html", "monthly", "0.8"),
    ("login.html", "monthly", "0.5"),
    ("about.html", "monthly", "0.6"),
    ("privacy.html", "yearly", "0.3"),
    ("terms.html", "yearly", "0.3"),
    ("models/index.html", "weekly", "0.9"),
    ("models/kimi.html", "weekly", "0.7"),
    ("models/xiaomi-mimo.html", "weekly", "0.7"),
    ("models/minimax.html", "weekly", "0.7"),
    ("models/zhipu-glm.html", "weekly", "0.7"),
    ("models/deepseek.html", "weekly", "0.7"),
    ("models/qwen.html", "weekly", "0.7"),
    ("models/vip-picks.html", "weekly", "0.8"),
    ("guides/index.html", "weekly", "0.8"),
    ("guides/lobechat.html", "weekly", "0.8"),
    ("guides/openclaw.html", "weekly", "0.8"),
    ("guides/openai-sdk.html", "weekly", "0.7"),
    ("guides/curl.html", "weekly", "0.6"),
    ("guides/nodejs.html", "weekly", "0.6"),
    ("guides/powershell.html", "weekly", "0.6"),
    ("guides/n8n.html", "weekly", "0.6"),
    ("guides/dify.html", "weekly", "0.6"),
]


def lastmod_for(rel: str) -> str:
    p = ROOT / rel
    if p.exists():
        return date.fromtimestamp(p.stat().st_mtime).isoformat()
    return TODAY


def main() -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for rel, freq, pri in PAGES:
        name = Path(rel).name
        if name in EXCLUDE:
            continue
        if not (ROOT / rel).exists():
            print("skip missing", rel)
            continue
        loc = f"{BASE}/{rel}"
        lm = lastmod_for(rel)
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{lm}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{pri}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    out = ROOT / "sitemap.xml"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", out, "urls", sum(1 for x in lines if "<loc>" in x))


if __name__ == "__main__":
    main()
