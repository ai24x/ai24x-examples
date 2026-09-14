# -*- coding: utf-8 -*-
import re
from pathlib import Path

root = Path(r"E:/AI24X/ai24x-website/ai24x01/web")
loc = (root / "config/locales.js").read_text(encoding="utf-8")
en = loc.split("var en = {", 1)[1].split("var ja", 1)[0]
keys = set(re.findall(r'"([^"]+)":', en))
missing = []
for p in root.glob("*.html"):
    t = p.read_text(encoding="utf-8")
    for m in re.finditer(r'data-i18n(?:-html|-placeholder)?="([^"]+)"', t):
        k = m.group(1)
        if k not in keys:
            missing.append((p.name, k))
print("en keys", len(keys))
print("missing", len(missing))
for x in missing:
    print(x)
