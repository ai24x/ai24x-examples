param(
    [int]$Port = 8000,
    [int]$OldPid = 0
)
$ErrorActionPreference = 'Continue'
$py = 'C:\Users\Admin\APPDATA\LOCAL\PROGRAMS\PYTHON\PYTHON314\PYTHON.EXE'
$wd = 'E:\AI24X\ai24x-website\ai24x01\api'

if ($OldPid -gt 0) {
    Stop-Process -Id $OldPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

$p = Start-Process -FilePath $py -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', "$Port") -WorkingDirectory $wd -WindowStyle Hidden -RedirectStandardOutput (Join-Path $wd "uvicorn-$Port.out.log") -RedirectStandardError (Join-Path $wd "uvicorn-$Port.err.log") -PassThru
Write-Output ("started PID=" + $p.Id)
Start-Sleep -Seconds 5
try {
    $h = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 8
    Write-Output ("health=" + ($h | ConvertTo-Json -Compress))
}
catch {
    Write-Output ("health FAIL: " + $_.Exception.Message)
    Get-Content (Join-Path $wd "uvicorn-$Port.err.log") -Tail 20 -ErrorAction SilentlyContinue
}
