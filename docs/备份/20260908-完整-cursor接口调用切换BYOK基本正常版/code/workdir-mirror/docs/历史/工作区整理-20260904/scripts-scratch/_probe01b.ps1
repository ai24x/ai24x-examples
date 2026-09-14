$ErrorActionPreference = "SilentlyContinue"
$sess = "C:\Users\Administrator\.openclaw\agents\main\sessions\fd4e1f78-5cac-475f-8e93-8cfcf76ba021.jsonl"
Write-Output "=== session info ==="
Get-Item $sess | Select-Object Length, LastWriteTime
Write-Output "=== last 2 lines (truncated 400 chars) ==="
Get-Content $sess -Tail 2 -Encoding UTF8 | ForEach-Object { if ($_.Length -gt 400) { $_.Substring(0,400) } else { $_ } }
Write-Output "=== out/err logs ==="
Get-Item "C:\Users\Administrator\ops\20260822-01指令-正式启动GitHub官方号注册.md.out.log","C:\Users\Administrator\ops\20260822-01指令-正式启动GitHub官方号注册.md.err.log" | Select-Object Name, Length, LastWriteTime
Write-Output "=== node processes ==="
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Select-Object ProcessId, CreationDate, @{N='Cmd';E={$_.CommandLine}} | Format-List
