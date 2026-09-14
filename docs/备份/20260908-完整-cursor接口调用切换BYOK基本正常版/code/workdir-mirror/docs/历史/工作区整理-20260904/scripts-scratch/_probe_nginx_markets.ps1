$ErrorActionPreference = "Stop"
$conf = "C:\nginx\conf\nginx.conf"
$lines = Get-Content $conf
Write-Output "=== server blocks (server_name lines) ==="
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match "server_name\s+.*ai24x") {
    "{0}: {1}" -f ($i + 1), $lines[$i].Trim()
  }
}
Write-Output ""
Write-Output "=== markets server block (line range) ==="
$start = -1; $end = -1; $depth = 0
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match "server\s*\{" -and $i -gt 100) {
    # peek next 40 lines for markets
    $peek = ($lines[($i)..([math]::Min($i + 40, $lines.Count - 1))] -join "`n")
    if ($peek -match "markets\.ai24x\.com" -and $start -lt 0) {
      $start = $i + 1
      $depth = 1
      for ($j = $i + 1; $j -lt $lines.Count; $j++) {
        if ($lines[$j] -match "\{") { $depth++ }
        if ($lines[$j] -match "\}") { $depth--; if ($depth -eq 0) { $end = $j + 1; break } }
      }
      break
    }
  }
}
if ($start -gt 0) {
  for ($k = $start - 1; $k -lt $end; $k++) {
    "{0}: {1}" -f ($k + 1), $lines[$k]
  }
} else {
  Write-Output "markets server block not found"
}
Write-Output ""
Write-Output "=== nginx.conf lines 60-105 (markets static block) ==="
for ($k = 59; $k -lt [math]::Min(105, $lines.Count); $k++) { "{0}: {1}" -f ($k + 1), $lines[$k] }
Write-Output ""
Write-Output "=== nginx.conf lines 250-340 (markets 443 block) ==="
for ($k = 249; $k -lt [math]::Min(340, $lines.Count); $k++) { "{0}: {1}" -f ($k + 1), $lines[$k] }
Write-Output "DONE"
