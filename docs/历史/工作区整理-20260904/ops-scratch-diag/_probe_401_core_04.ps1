$ErrorActionPreference = "Stop"
# Live probe: reproduce 401 + dump in-process settings via a tiny diagnostic endpoint alternative:
# call health, then try chat with a key from env file if present; also introspect via python under same NSSM AppDirectory.

Write-Host "=== HEAD / services ==="
Set-Location C:\ai24x01
git rev-parse HEAD
git rev-parse --short=12 HEAD

Write-Host "=== NSSM AppDirectory / AppParameters / AppEnvironmentExtra (raw bytes check) ==="
$nssm = "C:\Program Files\nssm\nssm.exe"
if (-not (Test-Path $nssm)) { $nssm = "C:\nssm\nssm.exe" }
foreach ($k in @("AppDirectory","AppParameters","AppEnvironmentExtra","ObjectName")) {
  $raw = & $nssm get AI24X-core $k 2>$null
  # nssm returns UTF-16; strip nulls for display
  if ($null -eq $raw) { Write-Host "$k=<null>"; continue }
  $s = ($raw | Out-String).Replace("`0","").Trim()
  if ($k -eq "AppEnvironmentExtra" -and $s.Length -gt 200) { $s = $s.Substring(0,200) + "..." }
  Write-Host "$k=$s"
}

Write-Host "=== Process cmdline sample ==="
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'run_prod|uvicorn|ai24x01\\api' } |
  Select-Object ProcessId, ParentProcessId, @{n='CL';e={$_.CommandLine.Substring(0,[Math]::Min(180,$_.CommandLine.Length))}} |
  Format-Table -AutoSize | Out-String -Width 220 | Write-Host

Write-Host "=== err log tail ==="
if (Test-Path C:\ai24x01\logs\ai24x-core.err.log) {
  Get-Content C:\ai24x01\logs\ai24x-core.err.log -Tail 30 -Encoding UTF8
}
if (Test-Path C:\ai24x01\logs\ai24x-core.out.log) {
  Write-Host "=== out log tail (401/chat) ==="
  Get-Content C:\ai24x01\logs\ai24x-core.out.log -Tail 50 -Encoding UTF8 | Select-String -Pattern "401|chat|invalid|API Key|auth" | Select-Object -Last 20
}

Write-Host "=== live curl completions without key ==="
try {
  $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8002/v1/chat/completions" -Method POST -ContentType "application/json" -Body '{"model":"flash","messages":[{"role":"user","content":"hi"}]}' -TimeoutSec 10
  Write-Host "status=$($r.StatusCode) body=$($r.Content)"
} catch {
  $resp = $_.Exception.Response
  if ($resp) {
    $code = [int]$resp.StatusCode
    $sr = New-Object IO.StreamReader($resp.GetResponseStream())
    $body = $sr.ReadToEnd()
    Write-Host "status=$code body=$body"
  } else { Write-Host $_.Exception.Message }
}

Write-Host "=== health ==="
try {
  (Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:8002/health" -TimeoutSec 5) | ConvertTo-Json -Compress
} catch { Write-Host $_.Exception.Message }
