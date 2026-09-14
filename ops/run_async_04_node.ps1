param([Parameter(Mandatory=$true)][string]$TaskFile)
# 后台启动 04 openclaw（node 直启，不依赖 cmd/不超时掐断）
$node = 'C:\Users\Administrator\AppData\Roaming\npm\node.exe'
if (-not (Test-Path $node)) { $node = (Get-Command node -ErrorAction SilentlyContinue).Source }
if (-not $node) { Write-Error 'node not found'; exit 1 }
$cli = 'C:\Users\Administrator\AppData\Roaming\npm\node_modules\openclaw\openclaw.mjs'
$log = "$TaskFile.out.log"
$args = @($cli, 'agent', '--agent', 'main', '--message-file', $TaskFile, '--json', '--timeout', '1800')
Start-Process -FilePath $node -ArgumentList $args -WindowStyle Hidden -WorkingDirectory 'C:\ai24x01' -RedirectStandardOutput $log -RedirectStandardError "$log.err"
Start-Sleep -Seconds 3
$len = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
"STARTED node=$node loglen=$len"
