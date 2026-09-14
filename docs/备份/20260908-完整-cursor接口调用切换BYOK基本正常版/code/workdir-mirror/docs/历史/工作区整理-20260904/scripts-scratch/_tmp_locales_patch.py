# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(r"E:/AI24X/ai24x-website/ai24x01")
loc = ROOT / "web/config/locales.js"
t = loc.read_text(encoding="utf-8")

def upsert_block(text, lang_marker, replacements):
    """replacements: list of (old, new) exact string swaps — safer than upsert."""
    for a, b in replacements:
        if a not in text:
            print("MISS", a[:70])
        else:
            text = text.replace(a, b)
            print("OK", a[:50])
    return text

zh = [
    (
        '"page.index.hero.title": "One API. Every AI. Pay Less.",',
        '"page.index.hero.title": "One API. Every AI. Spend Smarter.",',
    ),
    (
        '"page.index.hero.lead":\n      "一个接口对接多模型：自带 Key（BYOK）或托管计费。对比模型，按任务选性价比。",',
        '"page.index.hero.lead":\n      "一个接口对接多模型：自带 Key（BYOK）或托管计费。按任务选合适模型，少花冤枉钱。",',
    ),
    (
        '"page.index.cost.sub": "对比模型，按任务选性价比——BYOK 或托管，想简单就一张账单。",',
        '"page.index.cost.sub": "按工作负载匹配合适模型——BYOK Pro 智能路由；托管额度在此充值，少改代码也能控成本。",',
    ),
    (
        '"page.index.cost.c1p": "日常任务用高效模型；难任务再上旗舰模型。",',
        '"page.index.cost.c1p": "日常用高效模型，难任务再用旗舰——按任务匹配，而不是一律最贵。",',
    ),
    (
        '"page.index.cost.c2p": "统一 API 面——换模型不必每次重写应用。",',
        '"page.index.cost.c2p": "统一 API；BYOK Pro 可智能路由与故障切换，换模型不必重写应用。",',
    ),
    (
        '"page.help.q16p": "这是流式接口等待首个数据包时的正常保持连接行为，稍等即可。若约 10 分钟仍无内容，说明上游繁忙：可稍后重试，或改用 flash 等更稳定的模型。",',
        '"page.help.q16p": "这是流式接口等待首个数据包时的正常保持连接行为，稍等即可。若约 10 分钟仍无内容，说明模型服务繁忙：可稍后重试，或改用 flash 等更稳定的模型。",',
    ),
    (
        '"page.console.billSep.title": "两套体系：Token 充值 vs Markets Pro",',
        '"page.console.billSep.title": "三车道：托管额度 · BYOK · Markets",',
    ),
    (
        '"page.console.billSep.sub": "本页充值的是 API Token 余额（供 API Key、调试与聊天使用）。AI Markets Pro 是独立订阅：$9.9/周、$24.9/月 或 $199/年，PayPal 支付，在 markets.ai24x.com 开通与管理。",',
        '"page.console.billSep.sub": "托管额度：本页充值，供 API Key / 调试。BYOK Pro：在 open.ai24x.com 开通网关服务费。Markets Pro：本页订阅，解锁行情与 AI 点评。",',
    ),
    (
        '"page.console.products.sub": "先选产品，再选套餐与支付方式；支付后立即开通。",',
        '"page.console.products.sub": "三车道：托管额度（本页付）· BYOK Pro（去 AI Gateway 开通）· Markets Pro（本页付）。",',
    ),
    (
        '"auth.closed.banner":\n      "<strong>温馨提示</strong>：当前环境<strong>暂未开放</strong>注册与登录。",',
        '"auth.closed.banner":\n      "<strong>温馨提示</strong>：注册与登录<strong>暂时不可用</strong>，请稍后再试。",',
    ),
]

en = [
    (
        '"page.index.hero.title": "One API. Every AI. Pay Less.",',
        '"page.index.hero.title": "One API. Every AI. Spend Smarter.",',
    ),
    (
        '"page.index.cost.sub": "Compare models and choose the best price/performance for your workload — BYOK or managed, one bill when you want it simple.",',
        '"page.index.cost.sub": "Match each workload to the right model — smart routing on BYOK Pro; top up managed credits here to control spend without rewriting your app.",',
    ),
    (
        '"page.index.cost.c1p": "Route everyday work to efficient models; keep flagship models for the hard tasks.",',
        '"page.index.cost.c1p": "Use efficient models for everyday work; keep flagships for hard tasks — match the job, not the highest price.",',
    ),
    (
        '"page.index.cost.c2p": "One API surface — switch models without rewriting your app every time.",',
        '"page.index.cost.c2p": "One API surface; BYOK Pro adds smart routing and failover so you can switch models without rewriting your app.",',
    ),
    (
        '"page.console.billSep.title": "Two systems: API token top-up vs Markets Pro",',
        '"page.console.billSep.title": "Three lanes: managed credits · BYOK · Markets",',
    ),
    (
        '"page.console.billSep.sub": "This page tops up API token credits (used by API keys, Playground and chat). AI Markets Pro is a separate subscription — $9.9/week, $24.9/month or $199/year, paid via PayPal and managed on markets.ai24x.com.",',
        '"page.console.billSep.sub": "Managed credits: top up here for API keys & Playground. BYOK Pro: gateway fee on open.ai24x.com. Markets Pro: subscribe here for charts & AI briefs.",',
    ),
    (
        '"auth.closed.banner":\n      "<strong>Notice</strong>: Sign-up / sign-in are not open in this environment.",',
        '"auth.closed.banner":\n      "<strong>Notice</strong>: Sign-up / sign-in are temporarily unavailable.",',
    ),
]

# hero lead EN - find exact
for needle in [
    '"page.index.hero.lead":\n      "One integration for many models — BYOK or managed billing. Compare models and pick better price / performance.",',
    '"page.index.hero.lead":\n      "One API for leading models — BYOK or managed. Compare models, pick better price/performance.",',
]:
    if needle in t:
        t = t.replace(
            needle,
            '"page.index.hero.lead":\n      "One integration for many models — BYOK or managed. Match the right model to each job to spend smarter.",',
        )
        print("hero lead en ok")
        break
else:
    # try grep-like
    import re
    m = re.search(r'"page\.index\.hero\.lead":\s*\n\s*"[^"]+",', t)
    if m and "zh" not in m.group(0):
        pass
    print("hero lead en check manually if needed")

for a, b in zh + en:
    if a not in t:
        print("MISS", a[:80])
    else:
        t = t.replace(a, b)
        print("OK", a[:55])

# add new keys if missing
extras_zh = [
    ('"page.console.apiurl": "API 地址",', '"page.console.apiurl": "API 地址",\n    "page.console.apiurl.locked": "正式环境使用官方 API 地址（不可修改）。",'),
    ('"page.pricing.ctaConsole": "在账户中购买 / 管理 Key",', '"page.pricing.ctaConsole": "去账户充值",\n    "page.pricing.upgradeCtaWeekly": "试用周卡",'),
]
extras_en = [
    ('"page.console.apiurl": "API Base",', '"page.console.apiurl": "API Base",\n    "page.console.apiurl.locked": "Production uses the official API host (not editable).",'),
    ('"page.pricing.ctaConsole": "Buy / manage keys in Account",', '"page.pricing.ctaConsole": "Top up in Account",\n    "page.pricing.upgradeCtaWeekly": "Try weekly",'),
]

# products.sub may already be only in HTML default - also update locales if present EN
for a, b in [
    (
        '"page.console.products.sub": "Pick a product, then a plan — choose your payment method. Payment activates instantly.",',
        '"page.console.products.sub": "Three lanes: managed credits (pay here) · BYOK Pro (buy on AI Gateway) · Markets Pro (pay here).",',
    ),
    (
        '"page.pricing.devTitle": "Managed / Token API",',
        '"page.pricing.devTitle": "Managed credits",',
    ),
    (
        '"page.pricing.tokenTitle": "Developer plans (Token API)",',
        '"page.pricing.tokenTitle": "Top up Gateway credits in Account. Keys & docs stay on AI Gateway.",',
    ),
    (
        '"page.pricing.devTitle": "托管 / Token 接口",',
        '"page.pricing.devTitle": "托管额度",',
    ),
    (
        '"page.pricing.tokenTitle": "开发者套餐（Token API）",',
        '"page.pricing.tokenTitle": "在账户充值 Gateway 额度；Key 与文档在 AI Gateway。",',
    ),
]:
    if a in t:
        t = t.replace(a, b)
        print("extra", a[:40])
    else:
        print("skip extra", a[:40])

for a, b in extras_zh + extras_en:
    if "apiurl.locked" in b and "apiurl.locked" in t:
        print("locked already")
        continue
    if "upgradeCtaWeekly" in b and "upgradeCtaWeekly" in t:
        print("weekly already")
        continue
    if a in t and b.split(",")[0] not in t[t.index(a):t.index(a)+200]:
        t = t.replace(a, b, 1)
        print("insert", b[:50])
    elif a not in t:
        print("MISS insert base", a[:50])

# auth.login.footer Console -> Account
t = t.replace(
    '"auth.login.footer": "<a href=\\"register.html\\">注册</a> · <a href=\\"forgot.html\\">忘记密码？</a> · <a href=\\"console.html\\">控制台</a>"',
    '"auth.login.footer": "<a href=\\"register.html\\">注册</a> · <a href=\\"forgot.html\\">忘记密码？</a> · <a href=\\"console.html\\">账户</a>"',
)
t = t.replace(
    '"auth.login.footer": "<a href=\\"register.html\\">Sign up</a> · <a href=\\"forgot.html\\">Forgot password?</a> · <a href=\\"console.html\\">Console</a>"',
    '"auth.login.footer": "<a href=\\"register.html\\">Sign up</a> · <a href=\\"forgot.html\\">Forgot password?</a> · <a href=\\"console.html\\">Account</a>"',
)

loc.write_text(t, encoding="utf-8", newline="\n")
print("locales written")
