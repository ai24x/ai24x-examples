# restart-local-services.ps1 - 本地三常驻服务(NSSM)隐藏后台重启 + 健康检查
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\restart-local-services.ps1
# 说明: 8000(AI24X-core) / 18011(AI24X-a1-api) / 18001(AI24X-a1-web) 均为 NSSM Windows 服务，
#       天生隐藏无 CMD 窗口。日常重启一律用本脚本，不要再手动开窗口起 python。
$ErrorActionPreference = 'Stop'
$services = 'AI24X-core','AI24X-a1-api','AI24X-a1-web'
$checks = @(
    @{ Name='core(8000)';         Url='http://127.0.0.1:8000/health' },
    @{ Name='a1-api(18011)';      Url='http://127.0.0.1:18011/health' },
    @{ Name='a1-web(18001)';      Url='http://127.0.0.1:18001/' },
    @{ Name='a1-web-bj(18001)';   Url='http://127.0.0.1:18001/bj/' },
    @{ Name='a1-web-daily(18001)';Url='http://127.0.0.1:18001/daily/' }
)
Write-Host '== 重启 NSSM 服务(隐藏后台) =='
foreach ($s in $services) {
    Write-Host ("- {0} ..." -f $s)
    Restart-Service -Name $s -Force
}
Write-Host '== 等待服务 Running =='
foreach ($s in $services) {
    $svc = Get-Service -Name $s
    $svc.WaitForStatus('Running', (New-TimeSpan -Seconds 30))
    Write-Host ("- {0}: {1}" -f $s, $svc.Status)
}
Write-Host '== 健康检查 =='
$allOk = $true
foreach ($c in $checks) {
    try {
        $r = Invoke-WebRequest -Uri $c.Url -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200) { Write-Host ("- {0}: HTTP 200 OK" -f $c.Name) }
        else { $allOk = $false; Write-Host ("- {0}: HTTP {1} FAIL" -f $c.Name, $r.StatusCode) }
    } catch {
        $allOk = $false
        Write-Host ("- {0}: ERROR {1}" -f $c.Name, $_.Exception.Message)
    }
}
if ($allOk) {
    Write-Host '全部正常：三服务均为 NSSM 隐藏后台，无 CMD 窗口。'
    exit 0
} else {
    Write-Host '存在异常，请检查上方输出。'
    exit 1
}
