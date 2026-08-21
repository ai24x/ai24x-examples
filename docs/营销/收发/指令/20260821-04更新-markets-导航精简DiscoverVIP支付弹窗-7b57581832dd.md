# 【04 更新部署验收】markets 导航精简 + Discover VIP 门禁 + 支付弹新窗 · 7b57581832dd

> 司令已提交并双推（gitee + origin 均为 `7b57581832dd`）；老板指令「04更新」放行。
> 执行人：副脑04（本机 C:\ai24x01）。本批只动 **markets 后端 py + markets 静态**：同步 `C:\sites\markets.ai24x.com`（app/index/pricing/screener 四页，先备份 .bak）+ 重启 **AI24X-markets-api(18012)**。**不涉及 www/core(8002)、open(18080)、共享版本号**（本批未改 locales/api/console/shell）。

## 一、背景
老板本机 QA 全绿后放行，本批四件事：
1. **导航精简**：markets 四页（index/app/pricing/screener）顶部导航统一为 Home(https://www.ai24x.com/index.html)/Pricing/Help/Console，去掉 Discover、Chart App 菜单；首页去掉 Google/Apple 注入（social-login 区块）。
2. **Discover VIP 门禁**：screener.html 增加 Pro 门禁（未登录→Sign in、免费→upgrade 引导、Pro→正常展示）；后端 `/api/screener` 增加 `billing.is_pro` 校验（无 token→401 missing_bearer_token、非 Pro→403 vip_required）。Discover 仍可从 app.html 评分条 CTA 与直达 URL 进入。
3. **支付醒目 + 弹新窗**：app.html 订阅面板三档套餐卡片化（周/月/年，月卡金色 POPULAR 徽章），支付统一 payhub 弹窗（微信/支付宝/PayPal/Creem），外链支付走 `payhub-open`（target=_blank 新窗口），删除整页跳转死代码 doCheckout。
4. **数据源文案清理收尾**：seo_gen.py 生成模板 source → aggregated market data（privacy 与 seo 静态页已在 be64a991 批清理并上线，本批只收尾生成器）；公网 sites 静态复查 Tencent/Eastmoney/Sina 残留为 0。
5. 新增 QA 脚本入库：`_qa_pay_ui_20260820.js`（27/27）、`_qa_mobile_compact_20260821.js`（26/26）、`_qa_nav_vip_20260821.js`（18/18），纯仓库文件无需部署。

## 二、副脑04 执行脚本（整段复制运行）
```powershell
# === AI24X 更新部署验收 · 目标 7b57581832dd（markets 导航/VIP/支付弹窗）===
$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$SRV_MK = "AI24X-markets-api"
$EXP = "7b57581832dd"
$SITES = "C:\sites\markets.ai24x.com"
$TAG = "20260821-navvip"

Set-Location $REPO

"--- 0) 本批路径如有本地改动：备份后 checkout ---"
$keyFiles = @(
  "p/markets/api/server/app/main.py",
  "p/markets/scripts/seo_gen.py",
  "p/markets/web/app.html",
  "p/markets/web/index.html",
  "p/markets/web/pricing.html",
  "p/markets/web/screener.html"
)
foreach ($f in $keyFiles) {
    $dirty = git status --short -- $f
    if ($dirty) {
        $bn = ($f -replace "[\\/]", "_")
        Copy-Item "$REPO\$f" "C:\Users\Administrator\ops\dirty-$bn-$TAG" -Recurse -Force
        git checkout -- $f
        if ($LASTEXITCODE -ne 0) { Write-Host "!! checkout 失败: $f" -ForegroundColor Red; exit 1 }
        "dirty backup + checkout: $f"
    } else { "clean: $f" }
}

"--- 1) 拉取并校验目标提交 ---"
git pull
$HEAD = (git rev-parse --short=12 HEAD).Trim()
"HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { Write-Host "!! 目标 $EXP 不在 HEAD 历史中" -ForegroundColor Red; exit 1 }
git diff --quiet $EXP HEAD -- p/markets/api/server/app/main.py p/markets/scripts/seo_gen.py p/markets/web/app.html p/markets/web/index.html p/markets/web/pricing.html p/markets/web/screener.html
if ($LASTEXITCODE -ne 0) { Write-Host "!! 关键路径在 $EXP 之后仍有改动，停止" -ForegroundColor Red; exit 1 }
"target_verified=ok"

"--- 2) 同步 markets 静态到 nginx 服务目录（先备份）---"
foreach ($f in @("app.html", "index.html", "pricing.html", "screener.html")) {
    if (Test-Path "$SITES\$f") { Copy-Item "$SITES\$f" "$SITES\$f.bak-$TAG" -Force }
    Copy-Item "$REPO\p\markets\web\$f" "$SITES\$f" -Force
}

$sa = Get-Content "$SITES\app.html" -Raw -Encoding UTF8
$si = Get-Content "$SITES\index.html" -Raw -Encoding UTF8
$sp = Get-Content "$SITES\pricing.html" -Raw -Encoding UTF8
$ss = Get-Content "$SITES\screener.html" -Raw -Encoding UTF8

"sites_app_navhome=$($sa.Contains('data-i18n=\"nav.home\"')) sites_app_payhub=$($sa.Contains('id=\"payhub\"')) sites_app_plan3=$($sa.Contains('btn-sub-week') -and $sa.Contains('btn-sub-month') -and $sa.Contains('btn-sub-year')) sites_app_newwin=$($sa.Contains('id=\"payhub-open\" class=\"payhub-open\" href=\"#\" target=\"_blank\"'))"
"sites_app_no_oldnav=$(-not ($sa.Contains('nav.discover') -or $sa.Contains('data-i18n=\"nav.markets\"')))"
"sites_index_home=$($si.Contains('https://www.ai24x.com/index.html')) sites_index_no_social=$(-not ($si.Contains('social-login') -or $si.Contains('/v1/auth/providers')))"
"sites_pricing_home=$($sp.Contains('https://www.ai24x.com/index.html')) sites_pricing_no_old=$(-not $sp.Contains('/screener.html'))"
"sites_screener_gate=$($ss.Contains('id=\"sr-gate\"') -and $ss.Contains('id=\"gate-btn\"')) sites_screener_no_oldnav=$(-not $ss.Contains('nav.discover'))"
if (-not ($sa.Contains('id="payhub"') -and $sa.Contains('btn-sub-month') -and $sa.Contains('target="_blank"') -and $si.Contains('https://www.ai24x.com/index.html') -and -not $si.Contains('social-login') -and $ss.Contains('id="sr-gate"'))) {
    Write-Host "!! sites 静态文件内容校验失败" -ForegroundColor Red; exit 1
}

"--- 3) 数据源名残留复查（sites 全目录）---"
$leak = 0
Get-ChildItem $SITES -Recurse -Include *.html,*.js,*.py | ForEach-Object {
    $c = Get-Content $_.FullName -Raw
    foreach ($k in @("Tencent", "Eastmoney", "Sina")) {
        if ($c -match $k) { "LEAK: $($_.FullName) -> $k"; $leak++ }
    }
}
"sites_source_leak=$leak"
if ($leak -gt 0) { Write-Host "!! sites 仍有数据源名残留" -ForegroundColor Red; exit 1 }

"--- 4) 重启 markets (18012) ---"
Restart-Service $SRV_MK -Force
$okM = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 5
    try { $hM = Invoke-RestMethod -Uri "http://127.0.0.1:18012/health" -TimeoutSec 10 -UseBasicParsing; $okM = $true; break } catch {}
}
if (-not $okM) { Write-Host "!! markets /health 未就绪" -ForegroundColor Red; exit 1 }
"markets-health=$($hM.status)"
if ($hM.status -ne "ok") { Write-Host "!! markets 状态异常" -ForegroundColor Red; exit 1 }

"--- 5) 本地验收：/api/screener VIP 门禁 ---"
$noAuth = $null
try {
    $noAuth = Invoke-RestMethod -Uri "http://127.0.0.1:18012/api/screener?mode=all&limit=5" -TimeoutSec 30 -UseBasicParsing
    Write-Host "!! 无 token 竟返回 200" -ForegroundColor Red; exit 1
} catch {
    $st = $_.Exception.Response.StatusCode.value__
    $body = $_.ErrorDetails.Message
    "screener_noauth_status=$st body=$body"
    if ($st -ne 401 -or $body -notmatch "missing_bearer_token") { Write-Host "!! 无 token 应 401" -ForegroundColor Red; exit 1 }
}
$badTok = $null
try {
    $badTok = Invoke-RestMethod -Uri "http://127.0.0.1:18012/api/screener?mode=all&limit=5" -Headers @{ Authorization = "Bearer fake-token-qa" } -TimeoutSec 30 -UseBasicParsing
    Write-Host "!! 假 token 竟返回 200" -ForegroundColor Red; exit 1
} catch {
    $st2 = $_.Exception.Response.StatusCode.value__
    $body2 = $_.ErrorDetails.Message
    "screener_badtoken_status=$st2 body=$body2"
    if ($st2 -ne 401) { Write-Host "!! 假 token 应 401" -ForegroundColor Red; exit 1 }
}
"screener_gate_ok=1"

"--- 6) 冒烟：普通行情接口不回归（免费公开）---"
$q = Invoke-RestMethod -Uri "http://127.0.0.1:18012/api/quote?symbol=AAPL" -TimeoutSec 25 -UseBasicParsing
"quote_AAPL_code=$($q.code) name=$($q.data.name)"
if ($q.code -ne 0) { Write-Host "!! AAPL quote 回归失败" -ForegroundColor Red; exit 1 }

Write-Host "=== 部署成功 ✅ ===" -ForegroundColor Green
```

## 三、公网验收清单（04 服务器侧执行）
1. `https://markets.ai24x.com/` → 顶部菜单：Home / Pricing / Help / Console，**无 Discover、无 Chart App**；无 Google 登录按钮（首页）。
2. `https://markets.ai24x.com/app.html` → 顶部导航 Home/Pricing/Help/Console；`#sub` 三档套餐卡片（周/月/年），点升级弹 payhub 弹窗，支付按钮新窗口打开。
3. `https://markets.ai24x.com/pricing.html` → 导航 Home/Pricing，无 Chart App/Discover。
4. `https://markets.ai24x.com/screener.html` → 未登录显示 Sign in 门禁；登录免费账号显示 upgrade 引导；Pro 账号正常出扫描结果。
5. `https://markets.ai24x.com/api/screener`（无 Authorization）→ 401 missing_bearer_token。
6. 页脚与免责声明无 Tencent/Eastmoney/Sina 字样。

## 四、回滚预案
```powershell
git revert 7b57581832dd
Restart-Service AI24X-markets-api -Force
# markets 静态：恢复 C:\sites\markets.ai24x.com\*.bak-20260821-navvip 后重启 markets
```

## 五、群回执（统一格式，全 PASS 才发群）
- ✅ 已完成项：HEAD=7b57581832dd（merge-base + path diff 校验通过）、markets /health OK、sites 四页同步（app/index/pricing/screener）、导航无 Discover/Chart App、首页无 Google、screener 门禁 401/假 token 401、AAPL 行情无回归、sites 数据源名残留 0、群回执已发。
- ⚠️ 问题项：逐条列出（无则写「无」）。
- 附公网证据：markets 首页导航截图或 HTML 关键片段 + /api/screener 401 响应。
