$ErrorActionPreference = "Stop"
$work = "C:\ai24x01"
$EXP  = "31302f7"
Set-Location $work

Write-Host "== 0. move aside untracked receipt (keep .local backup) ==" -ForegroundColor Cyan
$f = Get-ChildItem -Path "$work\docs" -Recurse -Filter "*20260827-1929-04*out.md" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($f) {
  $dest = $f.FullName + ".local"
  Move-Item -LiteralPath $f.FullName -Destination $dest -Force
  Write-Host ("moved " + $f.Name + " -> .local")
} else {
  Write-Host "no untracked receipt found"
}

Write-Host "== 1. fetch + pull ==" -ForegroundColor Cyan
git fetch origin
git pull --ff-only origin master
if ($LASTEXITCODE -ne 0) {
  git fetch gitee
  git pull --ff-only gitee master
}
$HEAD = (git rev-parse --short=12 HEAD).Trim()
Write-Host "HEAD=$HEAD"
git merge-base --is-ancestor $EXP HEAD
if ($LASTEXITCODE -ne 0) { throw "HEAD missing target $EXP" }

Write-Host "== 2. marker check ==" -ForegroundColor Cyan
$raw = Get-Content (Join-Path $work "p\open\web\console.html") -Raw -Encoding UTF8
if ($raw -notlike "*#modal-pay-channels .pay-ico*") { throw "missing pay-ico css marker" }
Write-Host "marker OK" -ForegroundColor Green

Write-Host "== 3. restart AI24X-open-api ==" -ForegroundColor Cyan
Restart-Service AI24X-open-api -ErrorAction Stop
Start-Sleep -Seconds 5

Write-Host "== 4. public verify ==" -ForegroundColor Cyan
$opC = (Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/console.html" -Headers @{ Accept = "text/html" }).Content
if ($opC -notlike "*#modal-pay-channels .pay-ico*") { throw "public open console.html missing pay-ico css" }
Write-Host "HOTFIX DONE" -ForegroundColor Green
Write-Host ("DONE EXP=" + $EXP + " HEAD=" + $HEAD) -ForegroundColor Green
