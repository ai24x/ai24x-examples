$ErrorActionPreference = "SilentlyContinue"
Write-Output "--- git HEAD (C:\ai24x01 生产仓库) ---"
Set-Location C:\ai24x01
git rev-parse --short=12 HEAD
Write-Output "--- git log -1 ---"
git log -1 --oneline
Write-Output "--- AI24X-core 服务状态 ---"
Get-Service AI24X-core -ErrorAction SilentlyContinue | Select-Object Status, Name | Format-Table -AutoSize | Out-String
Write-Output "--- health probe ---"
try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10; Write-Output ("status=" + $h.status + " commit=" + $h.commit + " build_stamp=" + $h.build_stamp) } catch { Write-Output ("health ERR: " + $_.Exception.Message) }
Write-Output "--- 是否存在两个并发 openclaw agent 进程 ---"
Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" | Where-Object { $_.CommandLine -match "openclaw|agent" } | ForEach-Object { Write-Output ("pid=" + $_.ProcessId + " cmd=" + $_.CommandLine.Substring(0, [Math]::Min(200, $_.CommandLine.Length))) }