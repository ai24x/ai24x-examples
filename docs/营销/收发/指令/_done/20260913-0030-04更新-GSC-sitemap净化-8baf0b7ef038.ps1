$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "8baf0b7ef038"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }
$sm = Get-Content "web\sitemap.xml" -Raw -Encoding UTF8
if ($sm -like "*guides/cursor.html*") { throw "www sitemap still has open guide cursor" }
if ($sm -notlike "*tools.html*") { throw "www sitemap missing tools.html" }
$osm = Get-Content "p\open\web\sitemap.xml" -Raw -Encoding UTF8
if ($osm -like "*register.html*") { throw "open sitemap still has register" }
$or = Get-Content "p\open\web\robots.txt" -Raw -Encoding UTF8
if ($or -notlike "*Disallow: /login.html*") { throw "open robots missing login disallow" }
$login = Get-Content "p\open\web\login.html" -Raw -Encoding UTF8
if ($login -notlike "*noindex*") { throw "open login missing noindex" }
$openSite = "C:\sites\open.ai24x.com"
if (Test-Path $openSite) {
  $bak = "$openSite.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
  robocopy $openSite $bak /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
  robocopy "$work\p\open\web" $openSite /E /NFL /NDL /NJH /NJS /nc /ns /np
  if ($LASTEXITCODE -ge 8) { throw "open robocopy failed $LASTEXITCODE" }
}
Restart-Service AI24X-core -Force
Start-Sleep -Seconds 8
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }
# 公网验收：带 cache-buster，避免 EO CDN 7 天缓存误判
$cb = Get-Date -Format "yyyyMMddHHmmss"
$pubSm = Invoke-WebRequest -UseBasicParsing -Uri ("https://www.ai24x.com/sitemap.xml?cb=" + $cb) -TimeoutSec 25
if ($pubSm.StatusCode -ne 200) { throw "www sitemap not 200" }
if ($pubSm.Content -like "*guides/cursor.html*") { throw "public www sitemap still has cursor guide" }
$pubOsm = Invoke-WebRequest -UseBasicParsing -Uri ("https://open.ai24x.com/sitemap.xml?cb=" + $cb) -TimeoutSec 25
if ($pubOsm.Content -like "*register.html*") { throw "public open sitemap still has register" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# ✅ 04更新完成｜GSC-sitemap净化｜EXP=8baf0b7ef038 HEAD=<HEAD> health=<commit>｜公网验收通过
