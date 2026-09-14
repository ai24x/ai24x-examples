# -*- coding: utf-8 -*-
from pathlib import Path

root = Path(r"e:/AI24X/ai24x-website/ai24x01/web/models")
old = (
    '<p class="mt-2"><a href="index.html">All China models</a> · '
    '<a href="../refer.html">Invite &amp; earn</a> · '
    '<a href="../help.html">Help</a></p>'
)
new = (
    '<p class="mt-2">Like it? <a href="../refer.html">Invite a teammate</a> — '
    "you both get signup tokens. · "
    '<a href="index.html">All China models</a> · '
    '<a href="../help.html">Help</a></p>'
)
for p in root.glob("*.html"):
    t = p.read_text(encoding="utf-8")
    n = t.replace(old, new)
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("ok", p.name)

idx = root / "index.html"
it = idx.read_text(encoding="utf-8")
needle = '<a class="btn" href="../guides/index.html">Integrations</a>'
add = needle + '\n          <a class="btn" href="../refer.html">Invite a teammate</a>'
if "Invite a teammate" not in it and needle in it:
    idx.write_text(it.replace(needle, add), encoding="utf-8")
    print("index")
print("done")
