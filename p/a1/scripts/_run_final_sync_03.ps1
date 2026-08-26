$ErrorActionPreference = "Continue"
$pkg = "C:\Users\Administrator\_a1_final_sync"
& C:\PYTHON314\PYTHON.EXE "$pkg\_apply_final_sync.py" "$pkg"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& C:\PYTHON314\PYTHON.EXE "$pkg\_verify_final_sync.py" "$pkg"
if ($LASTEXITCODE -ne 0) {
  Write-Output "VERIFY_FAIL picks mismatch vs local pkg"
  exit 1
}
Restart-Service AI24X-a1-api
Start-Sleep -Seconds 8
(Get-Service AI24X-a1-api).Status
curl.exe -s http://127.0.0.1:8001/health
