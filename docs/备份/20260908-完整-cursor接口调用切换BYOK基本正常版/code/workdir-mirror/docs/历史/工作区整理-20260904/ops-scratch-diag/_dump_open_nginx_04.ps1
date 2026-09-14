$ErrorActionPreference = "Stop"
$conf = "C:\nginx\conf\nginx.conf"
Write-Host "=== open server blocks ==="
$lines = Get-Content -LiteralPath $conf -Encoding UTF8
$inOpen = $false
$depth = 0
$buf = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt $lines.Count; $i++) {
  $line = $lines[$i]
  if ($line -match 'server_name\s+.*open\.ai24x\.com') {
    # walk back to server {
    $start = $i
    while ($start -gt 0 -and $lines[$start] -notmatch '^\s*server\s*\{') { $start-- }
    $depth = 0
    for ($j = $start; $j -lt $lines.Count; $j++) {
      $l = $lines[$j]
      $buf.Add(("{0,5}|{1}" -f ($j+1), $l))
      $opens = ([regex]::Matches($l, '\{')).Count
      $closes = ([regex]::Matches($l, '\}')).Count
      $depth += $opens - $closes
      if ($j -gt $start -and $depth -le 0) { break }
    }
  }
}
$buf | ForEach-Object { Write-Host $_ }
Write-Host "=== done lines=$($buf.Count) ==="
