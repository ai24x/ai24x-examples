#!/usr/bin/env python3
import re
from pathlib import Path

for p in sorted(Path("web/blog").glob("*.html")):
    if p.name in ("index.html", "kimi-api-paypal-guide.html"):
        continue
    text = re.sub(r"<[^>]+>", " ", p.read_text(encoding="utf-8"))
    words = len(re.findall(r"[A-Za-z']+", text))
    print(f"{p.name}: {words} words")
