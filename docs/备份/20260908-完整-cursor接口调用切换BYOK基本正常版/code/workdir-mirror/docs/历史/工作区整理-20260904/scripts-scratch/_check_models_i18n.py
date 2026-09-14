# -*- coding: utf-8 -*-
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1]
t = (root / "web/config/locales.js").read_text(encoding="utf-8")
# Split on top-level lang keys: zh: { ... }, en: { ... }
parts = re.split(r"\n\s*(zh|en|ja|ko|de|fr|es)\s*:\s*\{", t)
# parts: [preamble, 'zh', body, 'en', body, ...]
lang_bodies = {}
for i in range(1, len(parts), 2):
    if i + 1 < len(parts):
        lang_bodies[parts[i]] = parts[i + 1]

def keys_of(body):
    return set(re.findall(r'"([^"]+)"\s*:', body))

zk = keys_of(lang_bodies.get("zh", ""))
ek = keys_of(lang_bodies.get("en", ""))
prefix = re.compile(r"^page\.(models|guides|help|console\.invite|console\.stat\.referrals\.hint)")
zkf = {k for k in zk if prefix.match(k)}
ekf = {k for k in ek if prefix.match(k)}
print("zh", len(zkf), "en", len(ekf))
print("zh only", sorted(zkf - ekf))
print("en only", sorted(ekf - zkf))

html_keys = set()
for f in (root / "web").rglob("*.html"):
    s = str(f).replace("\\", "/")
    if any(x in s for x in ("bak", "archive", "web_bak")):
        continue
    text = f.read_text(encoding="utf-8", errors="ignore")
    html_keys |= set(re.findall(r'data-i18n="([^"]+)"', text))

need = sorted(k for k in html_keys if prefix.match(k) or k.startswith("page.console.invite") or k == "page.console.copyInvite")
miss_zh = [k for k in need if k not in zk]
miss_en = [k for k in need if k not in ek]
print("miss zh", miss_zh)
print("miss en", miss_en)

sdk = (root / "web/guides/openai-sdk.html").read_text(encoding="utf-8")
assert sdk.count('id="site-header"') == 1
assert "</footer>" not in sdk.split("<main")[0]
print("openai-sdk header ok")
