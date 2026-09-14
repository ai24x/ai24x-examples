$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "d23b51d"
Set-Location $work

Write-Host "== 1. fetch + pull (04 only has origin) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks (www SEO) ==" -ForegroundColor Cyan
$robots = Get-Content (Join-Path $work "web\robots.txt") -Raw -Encoding UTF8
if ($robots -notlike "*Sitemap: https://www.ai24x.com/sitemap.xml*") { throw "robots missing sitemap line" }
$sm = Get-Content (Join-Path $work "web\sitemap.xml") -Raw -Encoding UTF8
if ($sm -notlike "*blog/what-is-ai-gateway.html*") { throw "sitemap missing hub url" }
if ($sm -like "*register.html*") { throw "sitemap still contains register.html" }
$idx = Get-Content (Join-Path $work "web\index.html") -Raw -Encoding UTF8
if ($idx -notlike "*AI Gateway guides*") { throw "index missing hub link section" }
$hub = Get-Content (Join-Path $work "web\blog\what-is-ai-gateway.html") -Raw -Encoding UTF8
if ($hub -notlike "*hreflang*") { throw "hub missing hreflang" }
if ($hub -notlike "*application/ld+json*") { throw "hub missing Article schema" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. restart AI24X-core (www static + api health commit) ==" -ForegroundColor Cyan
Restart-Service AI24X-core -ErrorAction Stop
Start-Sleep -Seconds 8

Write-Host "== 4. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$robotsPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/robots.txt").Content
if ($robotsPub -notlike "*Sitemap: https://www.ai24x.com/sitemap.xml*") { throw "public robots missing sitemap" }
$smPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/sitemap.xml").Content
if ($smPub -notlike "*blog/what-is-ai-gateway.html*") { throw "public sitemap missing hub" }
if ($smPub -like "*register.html*") { throw "public sitemap still has register" }
$www = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/" -Headers @{ Accept = "text/html" }).Content
if ($www -notlike "*AI Gateway guides*") { throw "public index missing hub section" }
$hubPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/blog/what-is-ai-gateway.html" -Headers @{ Accept = "text/html" }).Content
if ($hubPub -notlike "*hreflang*") { throw "public hub missing hreflang" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host "== 5. nginx manual (operator) ==" -ForegroundColor Yellow
Write-Host "REMINDER: shell pages 301->open; junk paths 404; old /blog/* 301; then GSC resubmit sitemap"

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# --- 04 openclaw：脚本成功后请在指挥部飞书群发一条精简确认（勿省略）---
# ✅ 04更新完成｜GSC收录优化｜EXP=d23b51d HEAD=<HEAD> health=<commit>｜公网验收通过｜待办：nginx 301+GSC
