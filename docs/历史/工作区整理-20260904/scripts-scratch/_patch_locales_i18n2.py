# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"E:/AI24X/ai24x-website/ai24x01/web/config/locales.js")
t = p.read_text(encoding="utf-8")

# Fix / upsert simple key replacements
pairs = [
    (
        '"page.refer.sub": "回馈规则与提现方式以控制台与协议为准。",',
        '"page.refer.sub": "注册双方各送 5000 token；被邀请人首次充值后再按一级 10%、二级 2% 结算返利。",',
    ),
    (
        '"page.console.actions.refresh": "刷新",',
        '"page.console.actions.refresh": "刷新数据",',
    ),
    (
        '"page.console.apiurl": "API 基址",',
        '"page.console.apiurl": "API Base",',
    ),
    (
        '"page.console.modal.saveSub": "完整密钥只显示这一次。关闭后无法再查看，请复制到安全处。",',
        '"page.console.modal.saveSub": "完整密钥<strong>只显示这一次</strong>。关闭后无法再查看，请复制到安全处。",',
    ),
    (
        '"page.console.sub":\n      "Manage your API access and usage in one place (more features coming).",',
        '"page.console.sub": "Manage Token balance, API keys, and plans.",',
    ),
    (
        '"page.console.stat.balance.sub": "Available credits & account balance",',
        '"page.console.stat.balance.sub": "Wallet available credits",',
    ),
    (
        '"page.console.stat.calls.sub": "Today / recent activity",',
        '"page.console.stat.calls.sub": "Recent consume entries",',
    ),
    (
        '"page.console.stat.keys.sub": "Count & management",',
        '"page.console.stat.keys.sub": "Active keys",',
    ),
    (
        '"page.console.stat.referrals.sub": "Invites & rewards overview",',
        '"page.console.stat.referrals.sub": "Invite code: ",',
    ),
    (
        '"page.console.apisettings.title": "API settings",',
        '"page.console.apisettings.title": "Call settings",',
    ),
    (
        '"page.console.actions.refresh": "Refresh",',
        '"page.console.actions.refresh": "Refresh data",',
    ),
    (
        '"page.console.modal.saveSub": "The full key is shown only once. Copy it to a safe place.",',
        '"page.console.modal.saveSub": "The full key is shown <strong>only once</strong>. Copy it to a safe place.",',
    ),
    (
        '"page.refer.sub":\n      "Rules and payout methods follow the console and agreements.",',
        '"page.refer.sub": "Both sides get 5000 tokens on signup; after the invitee\'s first top-up, earn 10% L1 / 2% L2.",',
    ),
]

for a, b in pairs:
    if a in t:
        t = t.replace(a, b, 1)
        print("OK", a[:50].replace("\n", " "))
    else:
        print("MISS", a[:50].replace("\n", " "))

zh_more = '''
    "auth.register.localBanner": "<strong>本地预览</strong>：邮箱注册已开放。未配置 SMTP 时验证码显示在下方卡片；配置 SMTP 后将发到真实邮箱。",
    "auth.register.codeSentSmtp": "验证码已发送到邮箱，请查收（含垃圾箱）。",
    "auth.register.sendFail": "发送失败",
    "auth.register.fail": "注册失败",
    "page.console.chat.promptPh": "你好",
    "page.pricing.loading": "加载套餐中…",
    "page.pricing.loadFail": "套餐加载失败",
    "page.pricing.payReady": "可在线支付：请到控制台选择微信或支付宝。",
    "page.pricing.payMock": "当前为测试环境，可在控制台完成体验充值。",
    "page.pricing.payClosed": "套餐可浏览；支付暂未开放，请稍后再试。",
    "page.pricing.ctaShort": "去控制台",
    "page.dashboard.title": "正在前往用户控制台",
    "page.dashboard.sub": "账户、API Key 与用量等请在新版「用户控制台」中查看与管理。",
    "page.dashboard.open": "打开用户控制台",
    "page.dashboard.home": "返回首页",
    "page.404.sub": "页面不存在或链接已失效。",
    "page.404.home": "返回首页",
'''

en_more = '''
    "auth.register.localBanner": "<strong>Local preview</strong>: email sign-up is open. Without SMTP the code appears below; with SMTP it goes to your inbox.",
    "auth.register.codeSentSmtp": "Code sent to your email (check spam).",
    "auth.register.sendFail": "Failed to send",
    "auth.register.fail": "Sign-up failed",
    "page.console.chat.promptPh": "Hello",
    "page.pricing.loading": "Loading plans…",
    "page.pricing.loadFail": "Failed to load plans",
    "page.pricing.payReady": "Online payment is available in the console.",
    "page.pricing.payMock": "Test environment: try a purchase in the console.",
    "page.pricing.payClosed": "Plans are listed; payment is not open yet.",
    "page.pricing.ctaShort": "Open console",
    "page.dashboard.title": "Opening the console",
    "page.dashboard.sub": "Manage account, API keys, and usage in the console.",
    "page.dashboard.open": "Open console",
    "page.dashboard.home": "Back to home",
    "page.404.sub": "This page does not exist or the link is broken.",
    "page.404.home": "Back to home",
'''

if '"auth.register.localBanner"' not in t.split("var en")[0]:
    t = t.replace('    "common.prompt": "提示",', zh_more + '    "common.prompt": "提示",', 1)
    print("inserted zh_more")
else:
    print("zh_more exists")

parts = t.split("var en = {", 1)
if len(parts) == 2:
    head, rest = parts
    en_body = rest.split("var ja")[0]
    if '"auth.register.localBanner"' not in en_body:
        rest = rest.replace('    "common.prompt": "Prompt",', en_more + '    "common.prompt": "Prompt",', 1)
        t = head + "var en = {" + rest
        print("inserted en_more")
    else:
        print("en_more exists")

p.write_text(t, encoding="utf-8")
print("wrote", p)
