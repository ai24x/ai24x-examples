$ErrorActionPreference = "Stop"
Set-Location C:\ai24x01
Write-Host "=== 04 REPO ==="
git rev-parse HEAD
git rev-parse --short=12 HEAD
git log -1 --oneline
git status -sb
Write-Host "=== remotes ==="
git remote -v
Write-Host "=== origin/master ==="
git fetch origin master 2>&1 | Out-String | Write-Host
git rev-parse origin/master
git log -1 --oneline origin/master
Write-Host "=== sync ==="
$h = (git rev-parse HEAD).Trim()
$o = (git rev-parse origin/master).Trim()
Write-Host ("HEAD==origin: " + ($h -eq $o))
if ($h -ne $o) {
  Write-Host "behind/ahead:"
  git rev-list --left-right --count origin/master...HEAD
}
Write-Host "=== health ==="
try {
  $ph = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 10
  Write-Host ("core_commit=" + $ph.commit)
} catch { Write-Host ("health_err=" + $_.Exception.Message) }
try {
  $oh = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:18080/health" -TimeoutSec 10
  Write-Host ("open_health=" + ($oh | ConvertTo-Json -Compress))
} catch { Write-Host ("open_health_err=" + $_.Exception.Message) }
Write-Host "=== porcelain count ==="
$p = git status --porcelain
Write-Host ("count=" + @($p).Count)
$p | Select-Object -First 40 | ForEach-Object { Write-Host $_ }
