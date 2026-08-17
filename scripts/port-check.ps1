# AI24X port monitor: a1(8001) + markets(18012) + core(8002) + local 18001/18011/18013
$ErrorActionPreference = 'SilentlyContinue'
Write-Host "=== AI24X port check $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan
$ports = @(18001, 18011, 18013, 8001, 8002, 18012)
$fail = @()
foreach ($p in $ports) {
    $c = Get-NetTCPConnection -State Listen -LocalPort $p
    if ($c) {
        Write-Host ("[OK]   port {0} listening (PID {1})" -f $p, (($c.OwningProcess | Select-Object -Unique) -join ',')) -ForegroundColor Green
    }
    else {
        Write-Host ("[FAIL] port {0} not listening" -f $p) -ForegroundColor Red
        $fail += $p
    }
}
if ($fail.Count -gt 0) {
    Write-Host ("`nALERT: ports not listening -> {0}" -f ($fail -join ' ')) -ForegroundColor Red
    exit 1
}
else {
    Write-Host "`nAll ports OK." -ForegroundColor Green
    exit 0
}
