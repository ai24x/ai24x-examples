# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"E:/AI24X/ai24x-website/ai24x01/web/config/locales.js")
t = p.read_text(encoding="utf-8")

zh = """
    "page.partner.cta.primary": "申请合作",
    "page.partner.cta.secondary": "前往控制台",
    "page.partner.sec1.title": "合作方向",
    "page.partner.sec1.sub": "资源、渠道与联合运营，一事一议。",
    "page.partner.card1": "面向机构与超级节点开放合作洽谈。",
    "page.partner.card2": "资源接入、联合运营与分润机制一事一议。",
    "page.partner.card3": "请通过控制台工单或商务邮箱联系（上线后启用）。",
    "page.partner.sec2.title": "怎么开始",
    "page.partner.step1.t": "留下意向",
    "page.partner.step1.p": "注册账号并在控制台留下合作意向。",
    "page.partner.step2.t": "对齐方案",
    "page.partner.step2.p": "沟通资源、场景与分润口径。",
    "page.partner.step3.t": "签约落地",
    "page.partner.step3.p": "签署协议后接入资源并开始结算。",
    "page.partner.note": "最终规则以正式协议为准；本页为概览说明。",
"""

en = """
    "page.partner.cta.primary": "Apply to partner",
    "page.partner.cta.secondary": "Open console",
    "page.partner.sec1.title": "Where we partner",
    "page.partner.sec1.sub": "Capacity, channels, and co-ops — case by case.",
    "page.partner.card1": "Programs for institutions and anchor partners.",
    "page.partner.card2": "Capacity, co-marketing, and revenue share — case by case.",
    "page.partner.card3": "Contact via console tickets or business email when enabled.",
    "page.partner.sec2.title": "How it starts",
    "page.partner.step1.t": "Share interest",
    "page.partner.step1.p": "Create an account and leave a partner note in the console.",
    "page.partner.step2.t": "Align the deal",
    "page.partner.step2.p": "Align capacity, use cases, and share terms.",
    "page.partner.step3.t": "Sign and launch",
    "page.partner.step3.p": "Sign the agreement, connect resources, and settle.",
    "page.partner.note": "Final terms follow the signed agreement; this page is an overview.",
"""

if '"page.partner.cta.primary"' not in t.split("var en")[0]:
    t = t.replace(
        '"page.partner.b3": "请通过控制台工单或商务邮箱联系（上线后启用）。",',
        '"page.partner.b3": "请通过控制台工单或商务邮箱联系（上线后启用）。",' + zh,
        1,
    )
    print("zh partner inserted")
else:
    print("zh partner exists")

parts = t.split("var en = {", 1)
if len(parts) == 2:
    head, rest = parts
    en_body = rest.split("var ja")[0]
    if '"page.partner.cta.primary"' not in en_body:
        rest = rest.replace(
            '"page.partner.b3": "Contact via console tickets or business email when enabled.",',
            '"page.partner.b3": "Contact via console tickets or business email when enabled.",' + en,
            1,
        )
        t = head + "var en = {" + rest
        print("en partner inserted")
    else:
        print("en partner exists")

p.write_text(t, encoding="utf-8")
print("done")
