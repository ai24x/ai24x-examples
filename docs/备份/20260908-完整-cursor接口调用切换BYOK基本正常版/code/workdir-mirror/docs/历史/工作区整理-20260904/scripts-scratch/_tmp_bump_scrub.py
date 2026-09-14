# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(r"E:/AI24X/ai24x-website/ai24x01")
files = []
for base in [root / "web", root / "p/open/web"]:
    for name in [
        "index.html",
        "pricing.html",
        "console.html",
        "login.html",
        "register.html",
        "forgot.html",
        "help.html",
    ]:
        p = base / name
        if p.exists():
            files.append(p)
repls = [
    ("js/api.js?v=20260826r", "js/api.js?v=20260826s"),
    ("js/api.js?v=20260823d", "js/api.js?v=20260826s"),
    ("js/api.js?v=20260824a", "js/api.js?v=20260826s"),
    ("config/locales.js?v=20260826r", "config/locales.js?v=20260826s"),
    ("config/locales.js?v=20260826q", "config/locales.js?v=20260826s"),
    ("config/locales.js?v=20260821b", "config/locales.js?v=20260826s"),
    ("js/console.js?v=20260826r", "js/console.js?v=20260826s"),
    ("js/console.js?v=20260826q", "js/console.js?v=20260826s"),
]
for p in files:
    t = p.read_text(encoding="utf-8")
    nt = t
    for a, b in repls:
        nt = nt.replace(a, b)
    if nt != t:
        p.write_text(nt, encoding="utf-8", newline="\n")
        print("bumped", p.relative_to(root))

for rel in ["web/ai24x.html", "p/open/web/ai24x.html"]:
    p = root / rel
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    nt = re.sub(
        r"\s*<a class=\"link-btn\" href=\"[^\"]*token-admin\.html\"[^>]*>Token 管理</a>\s*",
        "\n",
        t,
    )
    if nt != t:
        p.write_text(nt, encoding="utf-8", newline="\n")
        print("removed admin link", rel)
    else:
        print("no admin link change", rel)

# register www: ensure err.message uses setAlertMessage where still innerHTML
for rel in ["web/register.html", "p/open/web/register.html", "web/forgot.html", "p/open/web/forgot.html"]:
    p = root / rel
    t = p.read_text(encoding="utf-8")
    nt = t
    nt = re.sub(
        r"box\.innerHTML = '<div class=\"alert alert-error\">' \+ \(err\.message \|\| ([^)]+)\) \+ '</div>';",
        r"AI24X_API.setAlertMessage(box, err.message || \1, false);",
        nt,
    )
    nt = re.sub(
        r"showMsg\(box, err\.message \|\| ([^,]+), false\);",
        r"showMsg(box, err.message || \1, false);",
        nt,
    )
    if nt != t:
        p.write_text(nt, encoding="utf-8", newline="\n")
        print("escape patched", rel)

print("done")
