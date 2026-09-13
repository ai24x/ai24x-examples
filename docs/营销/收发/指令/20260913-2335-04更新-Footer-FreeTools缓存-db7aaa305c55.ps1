$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "db7aaa305c55"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$idx = Get-Content "web\index.html" -Raw -Encoding UTF8
if ($idx -notlike "*shell.js?v=20260913b*") { throw "www index missing shell v=20260913b" }
$sh = Get-Content "web\js\shell.js" -Raw -Encoding UTF8
if ($sh -notlike "*footer.link.tools*") { throw "www shell missing footer tools" }
$openSite = "C:\sites\open.ai24x.com"
if (Test-Path $openSite) {
  robocopy "$work\p\open\web" $openSite /E /NFL /NDL /NJH /NJS /nc /ns /np
  if ($LASTEXITCODE -ge 8) { throw "open robocopy failed $LASTEXITCODE" }
}
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }
$cb = Get-Date -Format "yyyyMMddHHmmss"
$pub = Invoke-WebRequest -UseBasicParsing -Uri ("https://www.ai24x.com/index.html?cb=" + $cb) -TimeoutSec 25
if ($pub.Content -notlike "*shell.js?v=20260913b*") { throw "public index still old shell ?v=" }
$js = Invoke-WebRequest -UseBasicParsing -Uri ("https://www.ai24x.com/js/shell.js?v=20260913b&cb=" + $cb) -TimeoutSec 25
if ($js.Content -notlike "*footer.link.tools*") { throw "public shell missing tools link" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜Footer Free Tools缓存｜EXP=db7aaa305c55 HEAD=<HEAD> health=<commit>｜公网验收通过
