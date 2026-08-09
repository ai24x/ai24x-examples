# === AI24X 鍙镐护鐩磋繛 04 閮ㄧ讲娲惧彂锛堜富閫氶亾 v2锛?==
# 鐢ㄦ硶: powershell -File scripts\deploy04.ps1 <浠诲姟md鏂囦欢>
# 璇存槑: 璺宠繃涓昏剳涓浆, 鐩存帴 scp 鎸囦护鍒?04 骞?ssh 椹卞姩 04 鐨?openclaw 鎵ц閮ㄧ讲+楠屾敹+椋炰功缇ゅ洖鎵?
param([Parameter(Mandatory=$true)][string]$TaskFile)

$ErrorActionPreference = "Stop"
$SshHost = "Administrator@43.160.246.30"
$RemoteOps = "C:\Users\Administrator\ops"
$TaskName = Split-Path $TaskFile -Leaf
$RemoteTask = "$RemoteOps\$TaskName"
$Log = Join-Path (Split-Path $PSScriptRoot -Parent) "ops\deploy04-$(Get-Date -Format HHmmss).log"

Write-Host "==> scp 鎸囦护 -> 04" -ForegroundColor Cyan
scp -o ConnectTimeout=20 -o StrictHostKeyChecking=no $TaskFile "${SshHost}:${RemoteTask}"
if ($LASTEXITCODE -ne 0) { throw "scp 澶辫触" }

Write-Host "==> 椹卞姩 04 鎵ц (openclaw agent, timeout 600)..." -ForegroundColor Cyan
$cmd = "openclaw agent --agent main --message-file ${RemoteTask} --json --timeout 600"
$sshOut = ssh -o ConnectTimeout=20 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost $cmd 2>&1
$sshOut | Out-File -FilePath $Log -Encoding utf8
Write-Host "==> 瀹屾垚, 鏃ュ織: $Log" -ForegroundColor Green
$sshOut | Select-Object -Last 40
