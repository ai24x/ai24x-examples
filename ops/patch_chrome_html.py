import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
dirs = [root / "web", root / "p" / "open" / "web"]
new_v = "20260829a"
old_shell = ("20260828c", "20260828d", "20260828i", "20260828j")
old_base = ("20260828c",)

for base in dirs:
    if not base.is_dir():
        continue
    for p in base.rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        orig = t
        for ov in old_shell:
            t = t.replace(f"shell.js?v={ov}", f"shell.js?v={new_v}")
        for ov in old_base:
            t = t.replace(f"base.css?v={ov}", f"base.css?v={new_v}")
        for pat in (
            f'<script src="js/shell.js?v={new_v}"></script>',
            f'<script src="../js/shell.js?v={new_v}"></script>',
        ):
            if pat in t and "ai24x-chrome.js" not in t:
                chrome = pat.replace("shell.js", "ai24x-chrome.js")
                t = t.replace(pat, chrome + "\n  " + pat, 1)
        if t != orig:
            p.write_text(encoding="utf-8", data=t)
            print("updated", p.relative_to(root))

print("done")
