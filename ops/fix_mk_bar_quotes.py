import pathlib

root = pathlib.Path(__file__).resolve().parents[1] / "p" / "markets" / "web"
for p in root.rglob("*.html"):
    t = p.read_text(encoding="utf-8")
    n = t.replace('id=\\"mk-product-bar\\"', 'id="mk-product-bar"')
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("fixed", p.relative_to(root))
