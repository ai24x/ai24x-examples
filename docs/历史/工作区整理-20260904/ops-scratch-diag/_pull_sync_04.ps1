$ErrorActionPreference = "Continue"
Set-Location C:\ai24x01
Write-Host "=== before ==="
git rev-parse --short=12 HEAD
git log -1 --oneline

# Prefer pull; ignore wincredman noise if objects already reachable
$env:GIT_TERMINAL_PROMPT = "0"
git pull --ff-only origin master 2>&1 | ForEach-Object { Write-Host $_ }

Write-Host "=== after ==="
git rev-parse --short=12 HEAD
git log -1 --oneline
$h = (git rev-parse HEAD).Trim()
# compare to expected tip if origin ref updated
git rev-parse origin/master 2>$null
Write-Host ("HEAD=" + $h)

Write-Host "=== health ==="
try {
  $ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 10
  Write-Host ("core_commit=" + $ph.commit + " status=" + $ph.status)
} catch { Write-Host ("core_health_err=" + $_.Exception.Message) }
try {
  $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:18080/health" -TimeoutSec 10
  Write-Host ("open_health_status=" + [int]$r.StatusCode + " body=" + $r.Content.Substring(0, [Math]::Min(200, $r.Content.Length)))
} catch { Write-Host ("open_health_err=" + $_.Exception.Message) }

Write-Host "=== open 410 sanity ==="
try {
  Invoke-WebRequest -UseBasicParsing -Uri "https://open.ai24x.com/v1/models" -TimeoutSec 15 | Out-Null
  Write-Host "open_models=200_UNEXPECTED"
} catch {
  if ($_.Exception.Response) { Write-Host ("open_models=" + [int]$_.Exception.Response.StatusCode) }
  else { Write-Host $_.Exception.Message }
}

Write-Host "=== porcelain (prod paths) ==="
git status --porcelain -- api web p/open/api p/open/web p/markets/api p/markets/web scripts/deploy04.ps1 scripts/deploy04_direct.ps1 | ForEach-Object { Write-Host $_ }
