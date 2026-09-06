$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "ab2eaa9f0a63"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$loc = Get-Content "p\open\web\config\locales.js" -Raw -Encoding UTF8
if ($loc -notlike "*codex.tip9*") { throw "locales missing tip9" }
# ensure commas after tip8/tip11 (zh)
if ($loc -notmatch 'tip8":[^
]+",\s*"page.guides.codex.tip9"') { throw "zh tip8 missing comma before tip9" }
node --check "p\open\web\config\locales.js"
if ($LASTEXITCODE -ne 0) { throw "locales.js syntax fail" }
$idx = Get-Content "p\open\web\index.html" -Raw -Encoding UTF8
if ($idx -notlike "*locales.js?v=20260906c*") { throw "index missing locales v20260906c" }
if ($idx -notlike "*shell.js?v=20260906c*") { throw "index missing shell v20260906c" }
# static open site — no core restart required
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 15
$pub = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/index.html" -TimeoutSec 25
if ($pub.Content -notlike "*locales.js?v=20260906c*") { throw "public index missing locales v20260906c" }
$locP = Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/config/locales.js?v=20260906c" -TimeoutSec 30
$tmp = Join-Path $env:TEMP ("locales-check-" + [guid]::NewGuid().ToString() + ".js")
[System.IO.File]::WriteAllBytes($tmp, $locP.RawContentStream.ToArray())
node --check $tmp
if ($LASTEXITCODE -ne 0) { throw "public locales.js syntax fail" }
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜open locales语法修复｜EXP=ab2eaa9f0a63 HEAD=<HEAD> health=<commit>｜公网验收通过