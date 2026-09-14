$ErrorActionPreference = "Stop"
$TaskFile = "C:\Users\Administrator\ops\task-20260822-02-01-role-change.md"
Write-Output "=== EXISTS: $(Test-Path $TaskFile) ==="
Write-Output "=== RUN ==="
$out = & "C:\Users\Administrator\AppData\Roaming\npm\openclaw.cmd" agent --agent main --message-file $TaskFile --json --timeout 180 2>&1 | Out-String
Write-Output $out
