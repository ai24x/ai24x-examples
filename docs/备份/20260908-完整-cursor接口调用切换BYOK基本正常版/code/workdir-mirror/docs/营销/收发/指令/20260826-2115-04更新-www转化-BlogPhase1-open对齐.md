# 需求类型：②需副脑办(副脑04)
# 需求描述：部署 www 转化版 + Gateway Phase1 Blog + open 首页对齐（静态目录）
# 验收标准：见下文「公网验收」；回执写 `docs/营销/收发/回复/` 同名 `-out.md`
# 期望时间：主脑 push 后当天

> 司令 / 平台官 → 副脑04 · 2026-08-26  
> **目标提交：`<EXP>`**（主脑 commit + push 后替换本占位；未填 SHA 勿执行）  
> 范围：`web/`（www）+ `p/open/web/`（open）静态；**不改** `.env`、不改 DB、不重启无关服务除非脚本要求

---

## 一、本次变更（摘要）

### www（`web/`）
- 转化首页 / 全站 Gateway-first CTA / theme-blue 统一
- Blog Phase1 五篇 + index：
  - `/blog/what-is-ai-gateway.html`
  - `/blog/openai-compatible-api.html`
  - `/blog/one-api-multiple-models.html`
  - `/blog/byok-ai-gateway.html`
  - `/blog/ai-api-cost-basics.html`
  - `/blog/index.html`（theme-blue + 列表）
- `web/sitemap.xml` 增补上述 URL，首页/定价 `lastmod=2026-08-26`
- 页脚增加 Blog 入口；首页底栏增加 `Gateway guides`；缓存 `locales/shell?v=20260826i`

### open（`p/open/web/`）
- Hero / title / OG：`One API. Every AI. Pay Less.`
- **canonical / og:url = `https://open.ai24x.com/`**（禁止再指向 www）

---

## 二、执行步骤（04 复制运行）

```powershell
$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "<EXP>"   # ← 替换为短 SHA
Set-Location $work

Write-Host "== 1. fetch + 含目标提交 ==" -ForegroundColor Cyan
git fetch origin
git pull
$HEAD = (git rev-parse --short=12 HEAD).Trim()
"HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD 不含目标提交 $EXP" }

Write-Host "== 2. 对齐静态目录到 HEAD（若生产用 checkout 目录策略，改为 checkout $EXP -- web/ p/open/web/） ==" -ForegroundColor Cyan
# 默认：已 pull 到含 $EXP 即可。若 04 惯用「不动 HEAD、只 checkout 目录」：
# git checkout $EXP -- web/ p/open/web/

Write-Host "== 3. 文件标记校验 ==" -ForegroundColor Cyan
$idx = Get-Content "$work\web\index.html" -Raw -Encoding UTF8
if (-not $idx.Contains("One API. Every AI. Pay Less.")) { throw "www index 缺 Gateway Hero" }
$blog = Get-Content "$work\web\blog\what-is-ai-gateway.html" -Raw -Encoding UTF8
if (-not $blog.Contains("What is an AI Gateway")) { throw "缺 Hub 文" }
$sm = Get-Content "$work\web\sitemap.xml" -Raw -Encoding UTF8
if (-not $sm.Contains("blog/what-is-ai-gateway.html")) { throw "sitemap 缺 Hub URL" }
$open = Get-Content "$work\p\open\web\index.html" -Raw -Encoding UTF8
if (-not $open.Contains('canonical" href="https://open.ai24x.com/"')) { throw "open canonical 未对齐" }
if ($open -match 'canonical" href="https://www\.ai24x\.com') { throw "open canonical 仍指向 www" }
Write-Host "文件标记通过" -ForegroundColor Green

Write-Host "== 4. 重启 AI24X-core（静态若由 Nginx 直出可跳过；有缓存时重启更稳） ==" -ForegroundColor Cyan
try {
  Restart-Service AI24X-core -ErrorAction Stop
  Start-Sleep -Seconds 6
  $h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
  Write-Host ("health commit=" + $h.commit) -ForegroundColor Yellow
} catch {
  Write-Host "⚠️ core 重启跳过或失败（若纯静态 Nginx 可忽略）：$_" -ForegroundColor Yellow
}

Write-Host "== 5. 公网验收 ==" -ForegroundColor Cyan
$www = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/" -Headers @{ Accept = "text/html" }).Content
if (-not $www.Contains("One API. Every AI. Pay Less.")) { throw "公网 www Hero 未更新（Ctrl+F5 / CDN 缓存？）" }
$hub = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/blog/what-is-ai-gateway.html" -Headers @{ Accept = "text/html" }).Content
if (-not $hub.Contains("AI Gateway")) { throw "公网 Hub 文 404 或未部署" }
$op = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/" -Headers @{ Accept = "text/html" }).Content
if (-not $op.Contains("open.ai24x.com")) { throw "公网 open 页异常" }
if (-not $op.Contains("One API. Every AI. Pay Less.")) { throw "公网 open Hero 未对齐" }
Write-Host "公网验收通过" -ForegroundColor Green

Write-Host "== 6. Sitemap 提醒（人工） ==" -ForegroundColor Cyan
Write-Host "请在 GSC / Bing 提交或重新抓取: https://www.ai24x.com/sitemap.xml"
Write-Host "✅ 完成：www 转化 + Blog Phase1 + open Gateway 对齐（EXP=$EXP）" -ForegroundColor Green
```

---

## 三、回滚（5 步）

1. 记录当前 HEAD / 备份目录（若有 `C:\backup\...`）
2. `git checkout <上一稳定 SHA> -- web/ p/open/web/`（或 `git reset --hard <上一 SHA>` — **仅当 04 确认无他人脏改**）
3. 重启 AI24X-core（如步骤 4）
4. 公网抽检：www Hero、open canonical、blog Hub
5. 群回执 ⚠️ 已回滚 + 原因

---

## 四、验收清单（群回执用）

- [ ] `www.ai24x.com` Ctrl+F5 可见 `One API. Every AI. Pay Less.`
- [ ] `www.ai24x.com/blog/` 列出 5 篇 Gateway 文 + Kimi
- [ ] `www.ai24x.com/blog/what-is-ai-gateway.html` 200
- [ ] `www.ai24x.com/sitemap.xml` 含上述 blog URL
- [ ] `open.ai24x.com` Hero 对齐；源码 canonical = `https://open.ai24x.com/`
- [ ] GSC/Bing：已提醒提交 sitemap（可次日）
