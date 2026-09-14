#!/usr/bin/env python3
import urllib.request
from pathlib import Path

KEYS = [
    "pay-btn-title-row",
    'id === "token"',
    "renderProducts",
    "Top up here",
    "plans-card-primary",
    "billingProducts",
]


def read_url(url: str) -> str:
    if url.startswith("file:"):
        p = url.replace("file:///", "").replace("/", "\\")
        return Path(p).read_text(encoding="utf-8")
    return urllib.request.urlopen(url, timeout=25).read().decode("utf-8", "replace")


for label, url in [
    ("www_prod", "https://www.ai24x.com/js/console.js"),
    ("open_prod", "https://open.ai24x.com/js/console.js"),
    ("www_local", "file:///E:/AI24X/ai24x-website/ai24x01/web/js/console.js"),
    ("open_local", "file:///E:/AI24X/ai24x-website/ai24x01/p/open/web/js/console.js"),
]:
    t = read_url(url)
    hits = {k: k in t for k in KEYS}
    print(label, hits, "len", len(t))
