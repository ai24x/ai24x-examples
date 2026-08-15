# AI24X Markets 本地启动脚本（18012，隐藏窗口）
# 可选：AI24X_MARKETS_MODEL_KEY 从 E:\AI24X\_tmp\markets_test_creds.json 读取（本地联调用）
$ErrorActionPreference = "Stop"
$PY = "C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe"
$WD = "E:\AI24X\ai24x-website\ai24x01\p\markets\api\server"
$OUT = Join-Path $WD "uvicorn-18012.out.log"
$ERR = Join-Path $WD "uvicorn-18012.err.log"

$creds = "E:\AI24X\_tmp\markets_test_creds.json"
if ((Test-Path $creds) -and -not $env:AI24X_MARKETS_MODEL_KEY) {
    $env:AI24X_MARKETS_MODEL_KEY = (Get-Content $creds -Raw -Encoding UTF8 | ConvertFrom-Json).api_key
}

$old = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "port 18012" -and $_.Name -match "python" }
foreach ($p in $old) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

Start-Process -FilePath $PY -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "18012" `
    -WorkingDirectory $WD -WindowStyle Hidden -RedirectStandardOutput $OUT -RedirectStandardError $ERR

$ok = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 1
    try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:18012/health" -TimeoutSec 3 -UseBasicParsing; $ok = $true; break } catch {}
}
if (-not $ok) { Write-Error "markets 18012 health not ready"; exit 1 }
$h | ConvertTo-Json -Compress
