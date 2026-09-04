\xef\xbb\xbf# 【03 更新】复盘空栏回退 / 大盘提示 / 完整重扫
# EXP=e10047cc8ca9
# 03: 123.207.199.238 · C:\ai24x01 · AI24X-a1-api (8001)

$ErrorActionPreference = "Stop"
$REPO = "C:\ai24x01"
$SRV  = "AI24X-a1-api"
$EXP  = "e10047cc8ca9"
Set-Location $REPO

$FILES = @(
  "p\a1\web\gd.html",
  "p\a1\web\m\gd.html",
  "p\a1\web\js\bjscreener.js",
  "p\a1\web\css\bjscreener.css",
  "p\a1\api\server\app\bj_screener.py",
  "p\a1\api\server\app\main.py"
)
$BK = "C:\backup\ai24x_a\$(Get-Date -Format yyyyMMdd)_pre_stale_mlpb_$EXP"
New-Item -ItemType Directory -Force -Path $BK | Out-Null
foreach ($x in $FILES) {
  $full = Join-Path $REPO $x
  if (Test-Path $full) {
    $chg = git -C $REPO status --porcelain -- $x
    if ($chg) {
      Copy-Item $full (Join-Path $BK ((Split-Path $x -Leaf) + ".bak")) -Force
      git -C $REPO checkout -- $x
    }
  }
}

git pull origin master
if ($LASTEXITCODE -ne 0) { Write-Host "!! git pull 失败" -ForegroundColor Red; exit 1 }
$HEAD = (git rev-parse --short=12 HEAD).Trim()
"HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { Write-Host "!! HEAD 不含 $EXP" -ForegroundColor Red; exit 1 }

$gd = Get-Content (Join-Path $REPO "p\a1\web\gd.html") -Raw -Encoding UTF8
if (-not $gd.Contains("bjscreener.js?v=161")) { Write-Host "!! 缺 js v=161" -ForegroundColor Red; exit 1 }
if (-not $gd.Contains("bjscreener.css?v=108")) { Write-Host "!! 缺 css v=108" -ForegroundColor Red; exit 1 }
$js = Get-Content (Join-Path $REPO "p\a1\web\js\bjscreener.js") -Raw -Encoding UTF8
if (-not $js.Contains("结构顺 · 成长走空")) { Write-Host "!! 缺成长走空文案" -ForegroundColor Red; exit 1 }
if (-not $js.Contains("mkt-fold-chev")) { Write-Host "!! 缺大盘下拉箭头" -ForegroundColor Red; exit 1 }
$bj = Get-Content (Join-Path $REPO "p\a1\api\server\app\bj_screener.py") -Raw -Encoding UTF8
if (-not $bj.Contains("_latest_archive_with_picks")) { Write-Host "!! 缺归档回退" -ForegroundColor Red; exit 1 }
if (-not $bj.Contains("_iter_archives_with_picks")) { Write-Host "!! 缺归档迭代" -ForegroundColor Red; exit 1 }
if (-not $bj.Contains('c.get("mainHit") or c.get("obsHit")')) { Write-Host "!! 缺 mlpb obsHit 放宽" -ForegroundColor Red; exit 1 }
$main = Get-Content (Join-Path $REPO "p\a1\api\server\app\main.py") -Raw -Encoding UTF8
if (-not $main.Contains("check_force_rescan_allowed")) { Write-Host "!! 缺完整重扫冷却" -ForegroundColor Red; exit 1 }

$beforePid = (Get-CimInstance Win32_Service -Filter "Name='$SRV'").ProcessId
Restart-Service $SRV -Force
$ok = $false; $afterPid = $beforePid
for ($i = 0; $i -lt 24; $i++) {
  Start-Sleep -Seconds 5
  try {
    $svc = Get-CimInstance Win32_Service -Filter "Name='$SRV'"
    if ($svc) { $afterPid = $svc.ProcessId }
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 10 -UseBasicParsing
    if ($afterPid -gt 0 -and $afterPid -ne $beforePid -and $h.ok) { $ok = $true; break }
  } catch {}
}
if (-not $ok) { Write-Host "!! 重启失败 before=$beforePid after=$afterPid" -ForegroundColor Red; exit 1 }

$pub = Invoke-WebRequest -Uri "https://a.ai24x.com/gd.html" -UseBasicParsing -TimeoutSec 25
if ($pub.StatusCode -ne 200 -or $pub.Content -notmatch 'bjscreener\.js\?v=161') { Write-Host "!! 公网 gd 非 v=161" -ForegroundColor Red; exit 1 }
if ($pub.Content -notmatch 'bjscreener\.css\?v=108') { Write-Host "!! 公网 gd 非 css v=108" -ForegroundColor Red; exit 1 }
$jsPub = Invoke-WebRequest -Uri "https://a.ai24x.com/js/bjscreener.js?v=161" -UseBasicParsing -TimeoutSec 25
if ($jsPub.Content -notmatch 'mkt-fold-chev') { Write-Host "!! 公网 js 缺箭头" -ForegroundColor Red; exit 1 }
$cssPub = Invoke-WebRequest -Uri "https://a.ai24x.com/css/bjscreener.css?v=108" -UseBasicParsing -TimeoutSec 25
if ($cssPub.StatusCode -ne 200) { Write-Host "!! 公网 css 失败" -ForegroundColor Red; exit 1 }

Write-Host "OK HEAD=$HEAD EXP=$EXP v=161/108 stale+mlpb+mkt-fold" -ForegroundColor Green
# ✅ 03更新完成｜复盘空栏回退与大盘提示｜EXP=e10047cc8ca9 HEAD=<HEAD>｜公网验收通过
