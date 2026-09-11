$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "737850c70c04"
Set-Location $work
git fetch origin
git pull --ff-only origin master
$HEAD = (git rev-parse --short=12 HEAD).Trim()
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing $EXP" }

$tm = Get-Content "api\token_mvp_service.py" -Raw -Encoding UTF8
if ($tm -notlike "*membership_note_zh*") { throw "missing membership_note_zh" }
if ($tm -notlike "*flash_needs_vip*") { throw "missing flash_needs_vip" }
$sv = Get-Content "api\services.py" -Raw -Encoding UTF8
if ($sv -notlike "*浣欓浠嶅彲鐢ㄤ簬 flash*") { throw "missing vip_required balance hint" }
$cj = Get-Content "web\js\console.js" -Raw -Encoding UTF8
if ($cj -notlike "*page.console.howto.creditsOk*") { throw "missing howto.creditsOk" }
if ($cj -notlike "*walletEmpty && bal.shared_enabled*") { throw "missing shared bootstrap only when empty" }
$ch = Get-Content "web\console.html" -Raw -Encoding UTF8
if ($ch -notlike "*console.js?v=20260911a*") { throw "missing console.js?v=20260911a" }
if ($ch -notlike "*locales.js?v=20260911a*") { throw "missing locales.js?v=20260911a" }
$loc = Get-Content "web\config\locales.js" -Raw -Encoding UTF8
if ($loc -notlike "*page.console.vip.expiredHint*") { throw "missing vip.expiredHint locale" }

Restart-Service AI24X-core -Force
if (Get-Service AI24X-open-api -ErrorAction SilentlyContinue) {
  Restart-Service AI24X-open-api -Force
}
Start-Sleep -Seconds 12
$ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 20
Write-Host ("health.commit=" + $ph.commit)
git merge-base --is-ancestor $EXP $ph.commit
if ($LASTEXITCODE -ne 0) { throw "health.commit missing $EXP" }

$pub = Invoke-RestMethod -UseBasicParsing -Uri "https://api.ai24x.com/health" -TimeoutSec 25
Write-Host ("public health=" + $pub.commit)
$www = Invoke-WebRequest -UseBasicParsing -Uri "https://www.ai24x.com/console.html" -TimeoutSec 25
if ($www.Content -notlike "*console.js?v=20260911a*") { throw "www console cache bust missing" }
if ($www.Content -notlike "*locales.js?v=20260911a*") { throw "www locales cache bust missing" }
Write-Host ("DONE EXP=$EXP HEAD=$HEAD health=$($ph.commit)") -ForegroundColor Green
# 鉁?04鏇存柊瀹屾垚锝淰IP杩囨湡涓庝綑棰濆彛寰勶綔EXP=737850c70c04 HEAD=<HEAD> health=<commit>锝滃叕缃戦獙鏀堕€氳繃

# ✅ 04更新完成｜VIP过期与余额口径｜EXP=737850c70c04 HEAD=<HEAD> health=<commit>｜公网验收通过
