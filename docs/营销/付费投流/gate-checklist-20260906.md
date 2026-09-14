# 投流门禁自查清单 — 2026-09-06
# 以下 7 项让 04 逐一核实，输出 PASS/FAIL + 说明

# --- 支付门禁 ---
# 1. PayPal Live 可用
#    确认：Dodo 后台 -> 支付方式 -> PayPal enabled? 
#    确认：PayPal 账号有真实商户状态？
#    确认：04 本机 curl 测试 /v1/billing/paypal/create-order 返回 200？

# 2. 商品定价已就绪
#    确认：Dodo live 商品 11 个全在（3 markets + 2 BYOK + 6 token）？
#    确认：收银台 prices 与实际定价一致？

# 3. Webhook 正常接收
#    确认：Dodo 后台 -> webhooks — 两个都 active？
#    确认：04 本机测试 POST /v1/billing/dodo/webhook 返回 200？

# --- 技术门禁 ---
# 4. 核心页面可访问
#    确认：curl www.ai24x.com/health -> commit
#    确认：curl open.ai24x.com/health -> status ok
#    确认：curl markets.ai24x.com/health
#    确认：curl a.ai24x.com/health

# 5. robots.txt 正确
#    确认：curl www.ai24x.com/robots.txt 含 Disallow /v1/ /api/ /r/

# 6. 注册流程可用
#    确认：www.ai24x.com/register.html 加载正常
#    确认：/v1/auth/register POST 测试返回 200（mock）

# 7. Google OAuth 回调通
#    确认：curl -s -o NUL -w "%%{redirect_url}" 
#          "https://www.ai24x.com/v1/auth/google/login?next=console.html"
#          应返回 accounts.google.com/...
