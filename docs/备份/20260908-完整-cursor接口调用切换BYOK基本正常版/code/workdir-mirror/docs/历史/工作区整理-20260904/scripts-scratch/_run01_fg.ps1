$ErrorActionPreference = "Stop"
$TaskFile = "C:\Users\Administrator\ops\20260822-01指令-正式启动GitHub官方号注册.md"
Write-Output "=== EXISTS ==="
Test-Path $TaskFile
Write-Output "=== RUN ==="
$out = & "C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd" agent --agent main --message-file $TaskFile --json --timeout 120 2>&1 | Out-String
Write-Output $out
