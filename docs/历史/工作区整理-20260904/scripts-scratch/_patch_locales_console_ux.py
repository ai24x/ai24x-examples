# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"e:/AI24X/ai24x-website/ai24x01/web/config/locales.js")
t = p.read_text(encoding="utf-8")
repls = [
    (
        '"page.console.balanceCta.body": "充值后可用 flash/pro 与名模；也可先在 Playground 选 shared 走每日免费共享（有日帽，与 VIP 日赠不同）。"',
        '"page.console.balanceCta.body": "充值后可用 flash/pro 与名模；也可先点「继续免费共享」，在试调用里选 shared（有日帽，与 VIP 日赠不同）。"',
    ),
    (
        '"page.console.chat.sub": "使用下方调用设置中的 API Key。档位 auto/flash/pro/ultra/shared；VIP 可点名中国模。"',
        '"page.console.chat.sub": "默认用当前登录账号发送。档位：auto/flash/pro/ultra/shared。仅勾选「用 API Key」时才走下方 Key（请用本账号 Key）。"',
    ),
    (
        '"page.console.apisettings.sub": "仅用于本页试调。请粘贴创建时保存的完整 Key；与充值/会员无关。"',
        '"page.console.apisettings.sub": "可选。试调用默认用登录会话；仅勾选「用 API Key」时才需要粘贴完整 Key。"',
    ),
    (
        '"page.console.balanceCta.body": "Top up for flash/pro and named models, or pick shared in Playground for the free daily pool (capped — not VIP daily bonus)."',
        '"page.console.balanceCta.body": "Top up for flash/pro and named models, or tap Continue free shared and choose shared in Try-call (capped — not VIP daily bonus)."',
    ),
    (
        '"page.console.chat.sub": "Uses the API key in call settings below. Tiers: auto / flash / pro / ultra / shared. VIP: named China models."',
        '"page.console.chat.sub": "Sends with your login by default. Tiers: auto/flash/pro/ultra/shared. Only uses the key below if you check Use API key."',
    ),
    (
        '"page.console.apisettings.sub": "Only for this Playground. Paste a full key you saved at creation; it is not tied to billing."',
        '"page.console.apisettings.sub": "Optional. Try-call uses your login by default. Paste a key only if you check Use API key."',
    ),
    (
        '"page.console.nav.playground": "Playground"',
        '"page.console.nav.playground": "Try call"',
    ),
]
for a, b in repls:
    if a in t:
        t = t.replace(a, b)
        print("replaced", a[:48])
    else:
        print("MISS", a[:64])

if '"page.console.chat.useKey"' not in t.split('"page.console.chat.model": "档位 / 点名"')[0][-200:]:
    pass
if t.count('"page.console.chat.useKey"') == 0:
    t = t.replace(
        '"page.console.chat.model": "档位 / 点名",',
        '"page.console.chat.model": "档位 / 点名",\n    "page.console.chat.useKey": "用 API Key 发送（默认走登录会话，勿粘贴其它账号的 Key）",',
        1,
    )
    t = t.replace(
        '"page.console.chat.model": "Tier / named",',
        '"page.console.chat.model": "Tier / named",\n    "page.console.chat.useKey": "Use API key to send (default: login session — do not paste another account key)",',
        1,
    )
    print("inserted useKey x2")
elif t.count('"page.console.chat.useKey"') == 1:
    if '"page.console.chat.model": "Tier / named"' in t and "Use API key to send" not in t:
        t = t.replace(
            '"page.console.chat.model": "Tier / named",',
            '"page.console.chat.model": "Tier / named",\n    "page.console.chat.useKey": "Use API key to send (default: login session — do not paste another account key)",',
            1,
        )
        print("inserted en useKey")

p.write_text(t, encoding="utf-8")
print("useKey count", t.count('"page.console.chat.useKey"'))
