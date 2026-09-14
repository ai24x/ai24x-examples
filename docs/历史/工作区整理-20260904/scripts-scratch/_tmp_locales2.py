# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"E:/AI24X/ai24x-website/ai24x01/web/config/locales.js")
t = p.read_text(encoding="utf-8")
reps = [
    (
        '"page.index.hero.lead":\n      "AI24X 公司中枢——同一账号贯通 AI Gateway、Markets 与计费。免费开始，再拿 API Key。",',
        '"page.index.hero.lead":\n      "一个接口对接多模型：BYOK 或托管计费。按任务选合适模型，少花冤枉钱。",',
    ),
    (
        '"page.index.hero.lead":\n      "The AI24X company hub — one account for AI Gateway, Markets, and billing. Start free, then get your API key.",',
        '"page.index.hero.lead":\n      "One integration for many models — BYOK or managed. Match the right model to each job to spend smarter.",',
    ),
    (
        '"page.index.hero.priceLine": "对比模型，选更合适的性价比——<a href=\\"pricing.html\\">查看套餐</a>。",',
        '"page.index.hero.priceLine": "按任务选模型控成本——<a href=\\"pricing.html\\">查看套餐</a>。",',
    ),
    (
        '"page.index.hero.priceLine": "Compare models and pick better price / performance — <a href=\\"pricing.html\\">see plans</a>.",',
        '"page.index.hero.priceLine": "Match models to the job to control spend — <a href=\\"pricing.html\\">see plans</a>.",',
    ),
    (
        '"page.pricing.devTitle": "托管 / Token API",',
        '"page.pricing.devTitle": "托管额度",',
    ),
    (
        '"page.pricing.tokenTitle": "开发者 Token 套餐（API）",',
        '"page.pricing.tokenTitle": "在账户充值 Gateway 额度；Key 与文档在 AI Gateway。",',
    ),
    (
        '"page.pricing.ctaConsole": "去账户购买 / 管理 Key",',
        '"page.pricing.ctaConsole": "去账户充值",\n    "page.pricing.upgradeCtaWeekly": "试用周卡",',
    ),
    (
        '"page.console.products.sub": "Gateway / BYOK 优先展示；再选 Markets 或其它套餐，支付完成立即开通。",',
        '"page.console.products.sub": "三车道：托管额度（本页付）· BYOK Pro（去 AI Gateway 开通）· Markets Pro（本页付）。",',
    ),
    (
        '"page.console.products.sub": "Gateway / BYOK listed first; then Markets and other plans. Payment activates instantly.",',
        '"page.console.products.sub": "Three lanes: managed credits (pay here) · BYOK Pro (buy on AI Gateway) · Markets Pro (pay here).",',
    ),
]
for a, b in reps:
    if a not in t:
        print("MISS", repr(a[:80]))
    else:
        t = t.replace(a, b, 1)
        print("OK")

if '"page.console.apiurl.locked"' not in t:
    t = t.replace(
        '"page.console.apiurl": "API Base",',
        '"page.console.apiurl": "API Base",\n    "page.console.apiurl.locked": "正式环境使用官方 API 地址（不可修改）。",',
        1,
    )
    t = t.replace(
        '"page.console.apiurl": "API base URL",',
        '"page.console.apiurl": "API base URL",\n    "page.console.apiurl.locked": "Production uses the official API host (not editable).",',
        1,
    )
    print("apiurl.locked inserted")

p.write_text(t, encoding="utf-8", newline="\n")
print("weekly", t.count("upgradeCtaWeekly"), "locked", t.count("apiurl.locked"))
