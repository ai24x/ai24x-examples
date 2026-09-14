# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"E:/AI24X/ai24x-website/ai24x01/web/config/locales.js")
t = p.read_text(encoding="utf-8")
repls = [
    (
        '"auth.login.localBanner": "<strong>本地预览</strong>：邮箱登录已开放。可用测试账号，或先去 <a href=\\"register.html\\">注册</a>。",',
        '"auth.login.localBanner": "可用邮箱登录，或先去 <a href=\\"register.html\\">注册</a>。",',
    ),
    (
        '"auth.register.otpLocal": "本地预览验证码（正式环境将发到邮箱）",',
        '"auth.register.otpLocal": "验证码",',
    ),
    (
        '"auth.register.otpHint": "已自动填入上方输入框，可直接设置密码完成注册。",',
        '"auth.register.otpHint": "已填入上方，请设置密码完成注册。",',
    ),
    (
        '"auth.register.localBanner": "<strong>本地预览</strong>：邮箱注册已开放。未配置 SMTP 时验证码显示在下方卡片；配置 SMTP 后将发到真实邮箱。",',
        '"auth.register.localBanner": "可用邮箱注册。验证码将发到你的邮箱。",',
    ),
    (
        '"page.pricing.payMock": "当前为测试环境，可在控制台完成体验充值。",',
        '"page.pricing.payMock": "可在控制台完成体验充值。",',
    ),
    (
        '"page.console.orders.sub": "待支付可「确认到账」；测试环境另有「模拟到账」",',
        '"page.console.orders.sub": "待支付订单可「确认到账」",',
    ),
    (
        '"auth.login.localBanner": "<strong>Local preview</strong>: email login is open. Use a test account or <a href=\\"register.html\\">sign up</a>.",',
        '"auth.login.localBanner": "Sign in with email, or <a href=\\"register.html\\">create an account</a>.",',
    ),
    (
        '"auth.register.otpLocal": "Local preview code (production sends email)",',
        '"auth.register.otpLocal": "Verification code",',
    ),
    (
        '"auth.register.otpHint": "Auto-filled above — set a password to finish.",',
        '"auth.register.otpHint": "Filled above — set a password to finish.",',
    ),
    (
        '"auth.register.localBanner": "<strong>Local preview</strong>: email sign-up is open. Without SMTP the code appears below; with SMTP it goes to your inbox.",',
        '"auth.register.localBanner": "Sign up with email. We will send a verification code to your inbox.",',
    ),
    (
        '"page.pricing.payMock": "Test environment: try a purchase in the console.",',
        '"page.pricing.payMock": "You can try a purchase in the console.",',
    ),
    (
        '"page.console.orders.sub": "Pending: confirm payment (mock top-up only in test)",',
        '"page.console.orders.sub": "Pending orders: confirm payment",',
    ),
]
for a, b in repls:
    if a not in t:
        print("MISS", a[:70].replace("\n", " "))
    else:
        t = t.replace(a, b, 1)
        print("OK", a[:50].replace("\n", " "))
p.write_text(t, encoding="utf-8")
print("done")
