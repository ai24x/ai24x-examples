$ErrorActionPreference = "SilentlyContinue"
$out = @()
$out += "=== gateway http health ==="
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:18789/health" -UseBasicParsing -TimeoutSec 10
  $out += "HTTP $($r.StatusCode) BODY=$($r.Content)"
} catch { $out += "ERR $($_.Exception.Message)" }
$out += "=== openclaw state tree (2 levels) ==="
Get-ChildItem "C:\Users\Administrator\.openclaw" -ErrorAction SilentlyContinue | ForEach-Object {
  $out += "D $($_.Name)"
  Get-ChildItem $_.FullName -ErrorAction SilentlyContinue | Select-Object -First 20 | ForEach-Object { $out += "  - $($_.Name) LEN=$($_.Length) T=$($_.LastWriteTime)" }
}
$out += "=== agent runs dir ==="
Get-ChildItem "C:\Users\Administrator\.openclaw\agents\main\runs" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object { $out += "$($_.Name) LEN=$($_.Length) T=$($_.LastWriteTime)" }
$out += "=== gateway proc threads ==="
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | ForEach-Object { $out += "PID=$($_.ProcessId) T=$($_.ThreadCount)" }
$out | Out-File -FilePath "C:\Users\Administrator\ops\_diag01b.txt" -Encoding UTF8
