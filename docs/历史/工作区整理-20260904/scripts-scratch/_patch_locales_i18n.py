# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"E:/AI24X/ai24x-website/ai24x01/web/config/locales.js")
t = p.read_text(encoding="utf-8")

zh_extra = r'''
    "page.console.actions.logout": "退出登录",
    "page.console.plans.title": "Token 套餐",
    "page.console.plans.loading": "加载中…",
    "page.console.orders.title": "我的订单",
    "page.console.orders.sub": "待支付订单可「模拟到账」或「确认到账」",
    "page.console.chat.title": "试调 chat/run",
    "page.console.chat.sub": "使用上方已保存的 API Key。品牌档：auto / flash / pro / ultra。",
    "page.console.chat.send": "发送",
    "page.console.chat.prompt": "Prompt",
    "page.console.modal.createTitle": "创建 API 密钥",
    "page.console.modal.createSub": "给这把密钥起个好记的名字，方便以后区分。",
    "page.console.modal.keyName": "密钥名称",
    "page.console.modal.keyNameDefault": "默认密钥",
    "page.console.modal.cancel": "取消",
    "page.console.modal.create": "创建",
    "page.console.modal.saveTitle": "请立即保存密钥",
    "page.console.modal.saveSub": "完整密钥只显示这一次。关闭后无法再查看，请复制到安全处。",
    "page.console.modal.copyKey": "复制密钥",
    "page.console.modal.saved": "我已保存",
    "page.console.modal.payTitle": "选择支付方式",
    "page.console.modal.paySub": "请选择微信或支付宝完成支付。",
    "page.console.modal.openAlipay": "在新窗口打开支付宝",
    "page.console.modal.closePay": "关闭",
    "auth.login.localBanner": "<strong>本地预览</strong>：邮箱登录已开放。可用测试账号，或先去 <a href=\"register.html\">注册</a>。",
    "auth.login.fail": "登录失败",
    "auth.login.footer": "<a href=\"register.html\">注册</a> · <a href=\"console.html\">控制台</a>",
    "auth.register.emailCode": "邮箱验证码",
    "auth.register.invite": "邀请码（可选）",
    "auth.register.invitePh": "选填",
    "auth.register.inviteHint": "填写有效邀请码：双方各送 5000 token。",
    "auth.register.otpLocal": "本地预览验证码（正式环境将发到邮箱）",
    "auth.register.otpHint": "已自动填入上方输入框，可直接设置密码完成注册。",
    "auth.register.codeReady": "验证码已就绪，请继续设置密码。",
    "auth.register.needEmail": "请先填写邮箱",
    "page.refer.code": "我的邀请码",
    "page.refer.copy": "复制",
    "page.refer.login": "登录查看",
    "page.refer.l1": "一级邀请",
    "page.refer.l1sub": "直接邀请人数",
    "page.refer.earn": "已获赠 token",
    "page.refer.pending": "含待结算：",
    "page.refer.needLogin": "请先登录后查看邀请数据。",
    "page.refer.loadFail": "加载失败",
'''

en_extra = r'''
    "page.console.actions.logout": "Log out",
    "page.console.plans.title": "Token plans",
    "page.console.plans.loading": "Loading…",
    "page.console.orders.title": "My orders",
    "page.console.orders.sub": "Pending orders: mock top-up or confirm payment",
    "page.console.chat.title": "Try chat/run",
    "page.console.chat.sub": "Uses the API key saved above. Models: auto / flash / pro / ultra.",
    "page.console.chat.send": "Send",
    "page.console.chat.prompt": "Prompt",
    "page.console.modal.createTitle": "Create API key",
    "page.console.modal.createSub": "Give this key a memorable name.",
    "page.console.modal.keyName": "Key name",
    "page.console.modal.keyNameDefault": "Default key",
    "page.console.modal.cancel": "Cancel",
    "page.console.modal.create": "Create",
    "page.console.modal.saveTitle": "Save your key now",
    "page.console.modal.saveSub": "The full key is shown only once. Copy it to a safe place.",
    "page.console.modal.copyKey": "Copy key",
    "page.console.modal.saved": "I saved it",
    "page.console.modal.payTitle": "Choose payment",
    "page.console.modal.paySub": "Pay with WeChat or Alipay.",
    "page.console.modal.openAlipay": "Open Alipay in a new window",
    "page.console.modal.closePay": "Close",
    "auth.login.localBanner": "<strong>Local preview</strong>: email login is open. Use a test account or <a href=\"register.html\">sign up</a>.",
    "auth.login.fail": "Login failed",
    "auth.login.footer": "<a href=\"register.html\">Sign up</a> · <a href=\"console.html\">Console</a>",
    "auth.register.emailCode": "Email code",
    "auth.register.invite": "Invite code (optional)",
    "auth.register.invitePh": "Optional",
    "auth.register.inviteHint": "Valid invite: both sides get 5000 tokens.",
    "auth.register.otpLocal": "Local preview code (production sends email)",
    "auth.register.otpHint": "Auto-filled above — set a password to finish.",
    "auth.register.codeReady": "Code ready — continue with your password.",
    "auth.register.needEmail": "Enter your email first",
    "page.refer.code": "My invite code",
    "page.refer.copy": "Copy",
    "page.refer.login": "Log in to view",
    "page.refer.l1": "Level-1 invites",
    "page.refer.l1sub": "Direct invitees",
    "page.refer.earn": "Tokens earned",
    "page.refer.pending": "Pending: ",
    "page.refer.needLogin": "Please log in to view referral data.",
    "page.refer.loadFail": "Failed to load",
'''

# Update key strings
replacements = [
    (
        '"auth.login.sub": "欢迎回来。",',
        '"auth.login.sub": "使用邮箱登录 AI24X（手机登录稍后开放）。",',
    ),
    (
        '"auth.closed.banner":\n      "<strong>温馨提示</strong>：主站<strong>暂未开放</strong>注册与登录，表单不可提交。推荐首发应用 <a href=\\"https://a.ai24x.com/?mode=register&amp;ch=phone\\" target=\\"_blank\\" rel=\\"noopener\\">AI 行情官｜灯塔版</a>。",',
        '"auth.closed.banner":\n      "<strong>温馨提示</strong>：主站<strong>暂未开放</strong>注册与登录。本地预览（127.0.0.1）已自动开放。",',
    ),
    (
        '"auth.register.sub": "创建账号，开始使用。",',
        '"auth.register.sub": "当前开放邮箱注册。手机短信注册稍后接入。",',
    ),
    (
        '"auth.register.password": "密码",',
        '"auth.register.password": "密码（至少 6 位）",',
    ),
    (
        '"auth.login.sub":\n      "Phone + password by default; switch to email + password if you prefer.",',
        '"auth.login.sub": "Sign in with email (phone login coming later).",',
    ),
    (
        '"auth.closed.banner":\n      "<strong>Notice</strong>: Main-site <strong>sign-up / sign-in are not open yet</strong>; forms cannot be submitted. Recommended first app: <a href=\\"https://a.ai24x.com/?mode=register&amp;ch=phone\\" target=\\"_blank\\" rel=\\"noopener\\">AI Market Watch (Lighthouse)</a>.",',
        '"auth.closed.banner":\n      "<strong>Notice</strong>: Main-site sign-up / sign-in are not open yet. Local preview (127.0.0.1) is enabled automatically.",',
    ),
    (
        '"auth.register.sub":\n      "Phone + password by default; switch to email + password if you prefer.",',
        '"auth.register.sub": "Email sign-up is open. SMS registration comes later.",',
    ),
    (
        '"auth.register.password": "Password",',
        '"auth.register.password": "Password (min 6 chars)",',
    ),
    (
        '"page.console.sub":\n      "Call APIs and review account info here (features ship incrementally).",',
        '"page.console.sub": "Manage Token balance, API keys, and plans.",',
    ),
    (
        '"page.console.actions.upgrade": "Upgrade",',
        '"page.console.actions.upgrade": "Pricing",',
    ),
    (
        '"page.console.apikey": "X-API-Key (optional)",',
        '"page.console.apikey": "API Key (full secret)",',
    ),
    (
        '"page.console.keys.copy": "Copy",',
        '"page.console.keys.copy": "Copy current key",',
    ),
    (
        '"page.console.keys.create": "Create",',
        '"page.console.keys.create": "Create key",',
    ),
    (
        '"page.console.activity.title": "Updates",',
        '"page.console.activity.title": "Ledger",',
    ),
    (
        '"page.console.activity.sub": "Your usage and billing summary will show up here.",',
        '"page.console.activity.sub": "Top-ups / bonuses / usage / referrals",',
    ),
    (
        '"page.console.apisettings.sub": "Basic settings for console and integrations.",',
        '"page.console.apisettings.sub": "API Base defaults to this origin; chat uses X-API-Key below.",',
    ),
    (
        '"page.console.stat.balance": "Balance",',
        '"page.console.stat.balance": "Balance (tokens)",',
    ),
    (
        '"page.console.stat.calls": "Usage",',
        '"page.console.stat.calls": "Recent usage",',
    ),
    (
        '"page.console.stat.referrals": "Referrals",',
        '"page.console.stat.referrals": "Level-1 invites",',
    ),
    (
        '"page.console.account.title": "Account overview",',
        '"page.console.account.title": "Account",',
    ),
    (
        '"page.console.account.user": "Account",',
        '"page.console.account.user": "User",',
    ),
    (
        '"page.console.account.plan": "Plan",',
        '"page.console.account.plan": "Plan tier",',
    ),
    (
        '"page.console.keys.sub": "Use this key to call the unified endpoint. Keep it safe.",',
        '"page.console.keys.sub": "Full key is shown only once at creation; list shows prefixes.",',
    ),
    (
        '"auth.register.codeSent": "Code sent. Check your SMS inbox.",',
        '"auth.register.codeSent": "Code sent. Check your email.",',
    ),
    (
        '"page.console.sub": "在控制台进行接口调用与信息查询（功能将持续完善）。",',
        '"page.console.sub": "管理 Token 余额、API Key 与套餐。",',
    ),
    (
        '"page.console.actions.upgrade": "续期 / 升级",',
        '"page.console.actions.upgrade": "定价说明",',
    ),
    (
        '"page.console.apikey": "X-API-Key（可选）",',
        '"page.console.apikey": "API Key（完整密钥）",',
    ),
    (
        '"page.console.keys.copy": "复制",',
        '"page.console.keys.copy": "复制当前 Key",',
    ),
    (
        '"page.console.keys.create": "创建",',
        '"page.console.keys.create": "创建密钥",',
    ),
    (
        '"page.console.activity.title": "动态",',
        '"page.console.activity.title": "用量流水",',
    ),
    (
        '"page.console.activity.sub": "近期数据与账单将在此汇总展示。",',
        '"page.console.activity.sub": "充值 / 赠送 / 消耗 / 返利",',
    ),
    (
        '"page.console.apisettings.title": "API 设置",',
        '"page.console.apisettings.title": "调用设置",',
    ),
    (
        '"page.console.apisettings.sub": "用于控制台与应用接入的基础配置。",',
        '"page.console.apisettings.sub": "API Base 默认同源；调用 chat 时使用下方 API Key（X-API-Key）。",',
    ),
    (
        '"page.console.account.title": "账户概览",',
        '"page.console.account.title": "账户",',
    ),
    (
        '"page.console.stat.balance": "余额",',
        '"page.console.stat.balance": "余额 (token)",',
    ),
    (
        '"page.console.stat.balance.sub": "可用额度与账户余额",',
        '"page.console.stat.balance.sub": "钱包可用额度",',
    ),
    (
        '"page.console.stat.calls": "调用量",',
        '"page.console.stat.calls": "近期消耗笔数",',
    ),
    (
        '"page.console.stat.calls.sub": "今日/最近使用情况",',
        '"page.console.stat.calls.sub": "近期调用消耗笔数",',
    ),
    (
        '"page.console.stat.keys.sub": "密钥数量与管理",',
        '"page.console.stat.keys.sub": "有效密钥数量",',
    ),
    (
        '"page.console.stat.referrals": "推荐",',
        '"page.console.stat.referrals": "一级邀请",',
    ),
    (
        '"page.console.stat.referrals.sub": "邀请与回馈概览",',
        '"page.console.stat.referrals.sub": "邀请码：",',
    ),
    (
        '"page.console.account.user": "账号",',
        '"page.console.account.user": "用户",',
    ),
    (
        '"page.console.account.plan": "套餐",',
        '"page.console.account.plan": "套餐档位",',
    ),
    (
        '"page.console.keys.sub": "用于调用 AI24X 统一接口，请妥善保管。",',
        '"page.console.keys.sub": "完整密钥仅在创建时返回一次；列表只显示前缀。",',
    ),
    (
        '"auth.closed.footerLogin":\n      "<a href=\\"register.html\\">注册</a> · <a href=\\"login.html\\">登录</a>",',
        '"auth.closed.footerLogin":\n      "<a href=\\"register.html\\">注册</a> · <a href=\\"console.html\\">控制台</a>",',
    ),
    (
        '"auth.closed.footerRegister":\n      "<a href=\\"login.html\\">登录</a> · <a href=\\"register.html\\">注册</a>",',
        '"auth.closed.footerRegister":\n      "<a href=\\"login.html\\">登录</a> · <a href=\\"console.html\\">控制台</a>",',
    ),
    (
        '"auth.closed.footerLogin":\n      "<a href=\\"register.html\\">Sign up</a> · <a href=\\"login.html\\">Log in</a>",',
        '"auth.closed.footerLogin":\n      "<a href=\\"register.html\\">Sign up</a> · <a href=\\"console.html\\">Console</a>",',
    ),
    (
        '"auth.closed.footerRegister":\n      "<a href=\\"login.html\\">Log in</a> · <a href=\\"register.html\\">Sign up</a>",',
        '"auth.closed.footerRegister":\n      "<a href=\\"login.html\\">Log in</a> · <a href=\\"console.html\\">Console</a>",',
    ),
]

for a, b in replacements:
    if a not in t:
        print("MISS:", a[:60].replace("\n", " "))
    else:
        t = t.replace(a, b, 1)
        print("OK:", a[:40].replace("\n", " "))

marker_zh = '    "common.prompt": "提示",'
marker_en = '    "common.prompt": "Prompt",'
if '"page.console.actions.logout"' not in t.split('var en')[0]:
    t = t.replace(marker_zh, zh_extra + marker_zh, 1)
    print("inserted zh_extra")
else:
    print("zh_extra already present")

# insert en_extra before en common.prompt (second occurrence after var en)
parts = t.split("var en = {", 1)
if len(parts) == 2:
    head, rest = parts
    if '"page.console.actions.logout"' not in rest.split("var ja")[0]:
        rest = rest.replace(marker_en, en_extra + marker_en, 1)
        t = head + "var en = {" + rest
        print("inserted en_extra")
    else:
        print("en_extra already present")

p.write_text(t, encoding="utf-8")
print("done", p)
