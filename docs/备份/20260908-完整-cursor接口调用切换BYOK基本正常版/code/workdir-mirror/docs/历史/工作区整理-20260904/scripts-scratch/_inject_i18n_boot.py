# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1] / "web"
for p in root.rglob("*.html"):
    rel = p.relative_to(root).as_posix()
    depth = rel.count("/")
    prefix = "../" * depth
    boot = f'<script src="{prefix}js/i18n-boot.js?v=20260802e"></script>'
    t = p.read_text(encoding="utf-8")
    o = t
    t = re.sub(
        r"[ \t]*<script src=\"(?:\.\./)*js/i18n-boot\.js\?[^\"]+\"></script>\r?\n?",
        "",
        t,
        flags=re.I,
    )
    m = re.search(r"(<meta\s+charset=[^>]+>\s*\r?\n?)", t, flags=re.I)
    if m:
        t = t[: m.end()] + "  " + boot + "\n" + t[m.end() :]
    else:
        t2, c = re.subn(r"(<head[^>]*>)", r"\1\n  " + boot, t, count=1, flags=re.I)
        if c:
            t = t2
    t = re.sub(r"js/i18n\.js\?v=[^\"']+", "js/i18n.js?v=20260802e", t)
    t = re.sub(r"js/shell\.js\?v=[^\"']+", "js/shell.js?v=20260802e", t)
    t = re.sub(r"css/base\.css\?v=[^\"']+", "css/base.css?v=20260802e", t)
    if t != o:
        p.write_text(t, encoding="utf-8")
        print("ok", rel)
print("done")
