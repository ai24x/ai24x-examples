$ErrorActionPreference = "SilentlyContinue"
$out = @()
$out += "=== cmd processes ==="
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" | ForEach-Object { $out += "PID=$($_.ProcessId) CMD=$($_.CommandLine)" }
$out += "=== node processes ==="
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | ForEach-Object { $out += "PID=$($_.ProcessId) CMD=$($_.CommandLine)" }
$out += "=== gateway status ==="
$out += (Get-Content "C:\Users\Administrator\ops\main-brain-status.json" -Raw -ErrorAction SilentlyContinue)
$out += "=== gateway debug tail ==="
$out += (Get-Content "C:\Users\Administrator\ops\gateway-debug.log" -Tail 20 -ErrorAction SilentlyContinue)
$out += "=== today sessions ==="
Get-ChildItem "C:\Users\Administrator\.openclaw\agents\main\sessions\*.jsonl" | Where-Object { $_.LastWriteTime -ge (Get-Date).AddHours(-24) } | ForEach-Object { $out += "$($_.Name) LEN=$($_.Length) T=$($_.LastWriteTime)" }
$out += "=== ops recent files ==="
Get-ChildItem "C:\Users\Administrator\ops\*" | Where-Object { $_.LastWriteTime -ge (Get-Date).AddHours(-3) } | ForEach-Object { $out += "$($_.Name) LEN=$($_.Length) T=$($_.LastWriteTime)" }
$out | Out-File -FilePath "C:\Users\Administrator\ops\_diag01.txt" -Encoding UTF8
