import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
pairs = [
    ("20260829b", "20260829c"),
    ("20260828a", "20260829c"),
    ("20260828b", "20260829c"),
]
files = [
    root / "web" / "console.html",
    root / "web" / "index.html",
]
for p in files:
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    for o, n in pairs:
        t = t.replace(f"?v={o}", f"?v={n}")
    p.write_text(t, encoding="utf-8")
    print("patched", p.name)

for base in [root / "web", root / "p/open/web", root / "p/markets/web"]:
    if not base.is_dir():
        continue
    for p in base.rglob("*"):
        if p.suffix not in (".html", ".js") or not p.is_file():
            continue
        t = p.read_text(encoding="utf-8")
        n = t.replace("?v=20260829b", "?v=20260829c")
        if n != t:
            p.write_text(n, encoding="utf-8")
            print("bumped", p.relative_to(root))

print("done")
