"""Inject mk-product-bar + chrome scripts into Markets HTML pages."""
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1] / "p" / "markets" / "web"
CHROME_CSS = """
    /* —— 全站产品切换条 —— */
    .ai24x-product-bar { border-bottom: 1px solid var(--border); background: rgba(10,12,16,.95); }
    .ai24x-product-bar-inner { max-width: 1200px; margin: 0 auto; padding: 6px 16px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .ai24x-product-bar-label { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); margin-right: 4px; }
    .product-switch { display: inline-flex; align-items: center; gap: 2px; }
    .product-switch a { font-size: 0.8rem; font-weight: 600; padding: 5px 10px; border-radius: 999px; text-decoration: none; }
    .product-switch a.is-on { color: #fff; background: var(--accent); }
    .product-switch a:not(.is-on) { color: var(--muted); }
    .product-switch a:not(.is-on):hover { color: var(--text); background: var(--panel2); }
"""
SCRIPTS = (
    '  <script src="/js/ai24x-chrome.js?v=20260829a"></script>\n'
    '  <script src="/js/www-links.js?v=20260829a"></script>\n'
    '  <script src="/js/mk-chrome.js?v=20260829a"></script>\n'
)

for p in root.rglob("*.html"):
    t = p.read_text(encoding="utf-8")
    orig = t
    if "mk-product-bar" not in t and "<body" in t:
        t = re.sub(r"(<body[^>]*>\s*)", r"\1  <div id=\"mk-product-bar\"></div>\n", t, count=1)
    if "ai24x-product-bar-inner" not in t and "</style>" in t:
        t = t.replace("</style>", CHROME_CSS + "\n  </style>", 1)
    if "/js/www-links.js" in t:
        t = re.sub(
            r'<script src="/js/www-links\.js\?v=[^"]+"></script>\s*',
            SCRIPTS,
            t,
            count=1,
        )
    if t != orig:
        p.write_text(t, encoding="utf-8")
        print("patched", p.relative_to(root))

print("done")
