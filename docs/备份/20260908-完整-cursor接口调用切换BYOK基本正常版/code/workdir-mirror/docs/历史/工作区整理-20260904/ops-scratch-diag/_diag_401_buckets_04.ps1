$ErrorActionPreference = "Stop"
Write-Host "=== chat status by 10-min bucket 19:00-21:20 ==="
$rx = [regex]'^(?<ts>2026-09-03 (?<h>\d{2}):(?<m>\d{2}):\d{2}).*POST /v1/(?:chat/completions|chat/run|responses) - Status: (?<st>\d+)'
$buckets = @{}
Get-Content C:\ai24x01\logs\ai24x-core.err.log -Encoding UTF8 | ForEach-Object {
  $m = $rx.Match($_)
  if (-not $m.Success) { return }
  $h = [int]$m.Groups['h'].Value
  $mi = [int]$m.Groups['m'].Value
  if ($h -lt 19 -or $h -gt 21) { return }
  if ($h -eq 21 -and $mi -gt 20) { return }
  $bucket = '{0:D2}:{1:D2}' -f $h, ([int]([math]::Floor($mi/10)*10))
  $st = $m.Groups['st'].Value
  if (-not $buckets.ContainsKey($bucket)) { $buckets[$bucket] = @{} }
  if (-not $buckets[$bucket].ContainsKey($st)) { $buckets[$bucket][$st] = 0 }
  $buckets[$bucket][$st]++
}
$buckets.Keys | Sort-Object | ForEach-Object {
  $b = $_
  $parts = $buckets[$b].GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Key)=$($_.Value)" }
  Write-Host "$b  $($parts -join ' ')"
}
