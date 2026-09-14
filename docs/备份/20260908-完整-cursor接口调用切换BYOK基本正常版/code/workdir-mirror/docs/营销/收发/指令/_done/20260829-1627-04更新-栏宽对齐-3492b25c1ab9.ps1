$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "3492b25c1ab9"
Set-Location $work

Write-Host "== 1. fetch + pull (origin only) ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker checks ==" -ForegroundColor Cyan
$mkCss = Get-Content (Join-Path $work "p\markets\web\css\mk-site.css") -Raw -Encoding UTF8
if ($mkCss -notlike "*--mk-max: 1140px*") { throw "mk-site.css mk-max not 1140" }
$mkIdx = Get-Content (Join-Path $work "p\markets\web\index.html") -Raw -Encoding UTF8
if ($mkIdx -notlike "*mk-site.css?v=20260829s*") { throw "markets index cache not 20260829s" }
$wwwPrice = Get-Content (Join-Path $work "web\pricing.html") -Raw -Encoding UTF8
if ($wwwPrice -like "*max-width:980px*") { throw "www pricing still has 980 narrow" }
if ($wwwPrice -notlike "*help-prose*") {
  # pricing may not have help-prose; ok
}
$wwwHelp = Get-Content (Join-Path $work "web\help.html") -Raw -Encoding UTF8
if ($wwwHelp -like "*max-width:860px*") { throw "www help still has 860 narrow" }
if ($wwwHelp -notlike "*help-prose*") { throw "www help missing help-prose" }
$openPrice = Get-Content (Join-Path $work "p\open\web\pricing.html") -Raw -Encoding UTF8
if ($openPrice -like "*max-width:980px*") { throw "open pricing still has 980 narrow" }
if ($openPrice -like "*max-width:1080px*") { throw "open pricing still has 1080 narrow" }
$openHelp = Get-Content (Join-Path $work "p\open\web\help.html") -Raw -Encoding UTF8
if ($openHelp -like "*max-width:820px*") { throw "open help still has 820 narrow" }
if ($openHelp -notlike "*help-prose*") { throw "open help missing help-prose" }
Write-Host "markers OK" -ForegroundColor Green

Write-Host "== 3. sync markets static ==" -ForegroundColor Cyan
$site = "C:\sites\markets.ai24x.com"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bak = "$site.bak-$stamp"
if (Test-Path $site) {
  Copy-Item -LiteralPath $site -Destination $bak -Recurse -Force
}
robocopy (Join-Path $work "p\markets\web") $site /E /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy markets failed code=$LASTEXITCODE" }
Write-Host "markets synced, backup=$bak"

Write-Host "== 4. restart services ==" -ForegroundColor Cyan
Restart-Service AI24X-core, AI24X-open-api, AI24X-markets-api -ErrorAction Stop
Start-Sleep -Seconds 12

Write-Host "== 5. public verify (on 04) ==" -ForegroundColor Cyan
$h = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -Headers @{ Accept = "application/json" }
$okCommit = $false
try { git merge-base --is-ancestor $EXP $h.commit; $okCommit = ($LASTEXITCODE -eq 0) } catch { $okCommit = $false }
if (-not $okCommit) { throw ("core commit mismatch: " + $h.commit) }

$mkHome = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/" -Headers @{ Accept = "text/html" }).Content
if ($mkHome -notlike "*mk-site.css?v=20260829s*") { throw "public markets missing mk-site 20260829s" }
$cssPub = (Invoke-WebRequest -UseBasicParsing -Uri "https://markets.ai24x.com/css/mk-site.css?v=20260829s" -Headers @{ Accept = "text/css" }).Content
if ($cssPub -notlike "*--mk-max: 1140px*") { throw "public mk-site mk-max not 1140" }
$wwwP = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/pricing.html" -Headers @{ Accept = "text/html" }).Content
if ($wwwP -like "*max-width:980px*") { throw "public www pricing still narrow 980" }
$wwwH = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/help.html" -Headers @{ Accept = "text/html" }).Content
if ($wwwH -like "*max-width:860px*") { throw "public www help still narrow 860" }
if ($wwwH -notlike "*help-prose*") { throw "public www help missing help-prose" }
$openP = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/pricing.html" -Headers @{ Accept = "text/html" }).Content
if ($openP -like "*max-width:980px*") { throw "public open pricing still narrow 980" }
$openH = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/help.html" -Headers @{ Accept = "text/html" }).Content
if ($openH -like "*max-width:820px*") { throw "public open help still narrow 820" }
if ($openH -notlike "*help-prose*") { throw "public open help missing help-prose" }
Write-Host "public verify OK" -ForegroundColor Green

Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD + " health=" + $h.commit) -ForegroundColor Green

# ✅ 04更新完成｜栏宽对齐｜EXP=3492b25c1ab9 HEAD=<HEAD> health=<commit>｜www+open+markets 公网验收通过