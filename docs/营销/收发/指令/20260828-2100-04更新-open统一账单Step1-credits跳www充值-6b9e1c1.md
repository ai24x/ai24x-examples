# 需求类型：②需副脑办(副脑04)
# 需求描述：open 站统一账单 Step1 —— AI Gateway credits 不再在 open 出售，控制台/定价页改为「去 www 充值」引导；BYOK 保留；顺手修 open 控制台手机端横向溢出
# 验收标准：open.ai24x.com console/pricing 公网含引导卡且不含 token 套餐表；locales.js?v=20260828k / base.css?v=20260828l / console.js?v=20260828j；open /health commit=6b9e1c1
# 期望时间：push 后立即 deploy04

> **目标提交：`6b9e1c1`**

## 变更摘要

- `p/open/web/console.html`：Billing 面板 `#plansGroupToken` 整块换成「AI Gateway credits 主站统一管理」引导卡（`#creditsTopupCta` 新窗跳 www#billing）；`#plansList`（token 套餐行容器）移除；`#ordersList` 长订单号换行 CSS
- `p/open/web/js/console.js`：`renderPlans` 把 BYOK 卡片渲染前置（`#plansList` 删除后 BYOK 仍正常）；`#creditsTopupCta` 本地环境感知（127.0.0.1 → 本地 www）
- `p/open/web/pricing.html`：`#tokenTable` 整块替换为 `#creditsSection` 引导卡；PayPal CTA 从 `#token-plans` 改指 `#billing`
- `p/open/web/config/locales.js`：新增 `page.console.plans.creditsRedirect*` / `page.pricing.credits*` 键（zh+en），`settleIntlBody` 去「或托管套餐」
- `p/open/web/css/base.css`：窄屏媒体查询 `.console-sidebar` 加 `min-width:0`（手机 375px 横向溢出修复）
- 版本号：locales.js 全站 **20260828k** / base.css 全站 **20260828l** / console.js **20260828j**

## 服务

- `Restart-Service AI24X-open-api`（open 18080，FastAPI mount 静态；**www core 8002 不动**）

## 执行步骤

1. 备份+清理脏改动（仅限本次涉及路径，防止 pull 冲突）：
   ```powershell
   $bk = "C:\Users\Administrator\ops\.bak-open-unified-billing-20260828"
   New-Item -ItemType Directory -Force -Path $bk | Out-Null
   git -C C:\ai24x01 status --short -- p/open/web | ForEach-Object {
     $rel = ($_ -replace '^\S+\s+','').Trim()
     if ($rel) {
       $src = Join-Path "C:\ai24x01" $rel
       if (Test-Path -LiteralPath $src) {
         $dst = Join-Path $bk ($rel -replace '[\\/]','__')
         Copy-Item -LiteralPath $src -Destination $dst -Force
         git -C C:\ai24x01 checkout -- $rel
       }
     }
   }
   ```
2. `git -C C:\ai24x01 pull`
3. HEAD 校验：`git -C C:\ai24x01 merge-base --is-ancestor 6b9e1c1 HEAD` → 返回 0 即通过（无输出=成功）
4. `Restart-Service AI24X-open-api -Force`，等待 10s
5. 公网验收（全部必须通过，逐条回执）：
   - `https://open.ai24x.com/health` → commit 以 `6b9e1c1` 开头
   - `https://open.ai24x.com/console.html` → 200，且含 `creditsTopupCta`，且**不含** `id="plansList"`
   - `https://open.ai24x.com/pricing.html` → 200，且含 `id="creditsSection"`，且**不含** `id="tokenTable"`
   - console.html 含 `locales.js?v=20260828k` + `base.css?v=20260828l` + `console.js?v=20260828j`
   - pricing.html 含 `locales.js?v=20260828k` + `base.css?v=20260828l`
   - 本地仓库扫残留：`git -C C:\ai24x01 grep -n "locales.js?v=20260828j\|locales.js?v=20260827d" -- p/open/web` → 无输出
   - www 回归（应无变化）：`https://www.ai24x.com/console.html` 200

## 群确认（04 必发）

```
✅ 04更新完成｜open统一账单Step1-credits跳www充值｜EXP=6b9e1c1 HEAD=<12位> health=<12位>｜locales 20260828k/base 20260828l/console 20260828j 公网通过
```
