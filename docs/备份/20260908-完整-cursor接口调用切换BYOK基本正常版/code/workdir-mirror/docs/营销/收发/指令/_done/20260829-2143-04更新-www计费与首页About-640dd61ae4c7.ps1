$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "640dd61ae4c7"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$idx = Get-Content -Raw -Encoding UTF8 (Join-Path $work "web\index.html")
if ($idx -notmatch 'locales\.js\?v=20260829u') { throw "index locales v missing 20260829u" }
if ($idx -notmatch '>MiMo<') { throw "index missing MiMo model tag" }
if ($idx -notmatch 'flow-ellipsis') { throw "index missing More ellipsis" }
$about = Get-Content -Raw -Encoding UTF8 (Join-Path $work "web\about.html")
if ($about -notmatch 'Spend Smarter') { throw "about missing Spend Smarter" }
if ($about -notmatch 'locales\.js\?v=20260829u') { throw "about locales v missing" }
$con = Get-Content -Raw -Encoding UTF8 (Join-Path $work "web\console.html")
if ($con -notmatch 'console\.js\?v=20260829t') { throw "console.js v missing 20260829t" }
if ($con -notmatch 'locales\.js\?v=20260829u') { throw "console locales v missing" }
$adm = Get-Content -Raw -Encoding UTF8 (Join-Path $work "web\token-admin.html")
if ($adm -match 'value="18958992226"') { throw "token-admin still has hardcoded admin phone" }
if ($adm -notmatch 'admCaptchaWrap') { throw "token-admin missing captcha UI" }
$pay = Get-Content -Raw -Encoding UTF8 (Join-Path $work "api\pay_products.py")
if ($pay -notmatch '0\.35') { throw "pay_products missing 0.35 anchor" }
if ($pay -match 'Token 套餐') { throw "pay_products still has Token 套餐" }
$main = Get-Content -Raw -Encoding UTF8 (Join-Path $work "api\main.py")
if ($main -notmatch 'AdminSmsSendBody') { throw "main missing AdminSmsSendBody" }
if ($main -notmatch 'captcha_required') { throw "admin auth mode missing captcha_required" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 4. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 5. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$wwwIdx = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/index.html").Content
if ($wwwIdx -notmatch 'locales\.js\?v=20260829u') { throw "www index locales not 20260829u" }
if ($wwwIdx -notmatch '>MiMo<') { throw "www index missing MiMo" }
$wwwAbout = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/about.html").Content
if ($wwwAbout -notmatch 'Spend Smarter') { throw "www about missing Spend Smarter" }
$wwwCon = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html").Content
if ($wwwCon -notmatch 'console\.js\?v=20260829t') { throw "www console.js not 20260829t" }
$mode = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/v1/admin/auth/mode"
if (-not ($mode.PSObject.Properties.Name -contains 'captcha_required')) { throw "auth/mode missing captcha_required" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# ✅ 04更新完成｜www计费首页About｜EXP=640dd61ae4c7 HEAD=<HEAD> health=<commit>｜www公网验收通过