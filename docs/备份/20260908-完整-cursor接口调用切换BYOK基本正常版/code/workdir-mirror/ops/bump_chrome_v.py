import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
old_v = "20260829a"
new_v = "20260829b"
patterns = ("ai24x-chrome.js", "shell.js", "mk-chrome.js", "base.css")
dirs = [root / "web", root / "p" / "open" / "web", root / "p" / "markets" / "web"]

for base in dirs:
    if not base.is_dir():
        continue
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in (".html", ".js", ".css"):
            continue
        t = p.read_text(encoding="utf-8")
        if old_v not in t:
            continue
        t2 = t.replace(f"?v={old_v}", f"?v={new_v}")
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            print("bumped", p.relative_to(root))

# a1 shell + css
for rel in ("p/a1/web/js/shell.js", "p/a1/web/css/base.css"):
    p = root / rel.replace("/", "\\") if False else root / rel
    if not p.exists():
        p = root / "p" / "a1" / "web" / ("js/shell.js" if "shell" in rel else "css/base.css")
    if p.exists() and "shell.js" in str(p):
        t = p.read_text(encoding="utf-8")
        t2 = t.replace("shell.js?v=57", "shell.js?v=58")
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            print("bumped a1 shell")

print("done")
