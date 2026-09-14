$ErrorActionPreference = "SilentlyContinue"
$sess = Get-ChildItem "C:\Users\Administrator\.openclaw\agents\main\sessions\*.jsonl" | Where-Object { $_.LastWriteTime -gt [datetime]"2026-08-23 17:00" } | Sort-Object LastWriteTime
Write-Output "=== SESSIONS AFTER 08-23 17:00 ==="
$sess | ForEach-Object { "{0}  {1}KB" -f $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm"), [math]::Round($_.Length/1KB) }
Write-Output ""
Write-Output "=== MATCHES: social-register ==="
$sess | ForEach-Object {
  $f = $_.FullName
  Select-String -Path $f -Pattern "social-register" -SimpleMatch | Select-Object -First 5 | ForEach-Object { "{0} :: {1}" -f $_.Filename, $_.Line.Substring(0, [math]::Min(220, $_.Line.Length)) }
}
Write-Output ""
Write-Output "=== MATCHES: Product Hunt ==="
$sess | ForEach-Object {
  $f = $_.FullName
  Select-String -Path $f -Pattern "Product Hunt" -SimpleMatch | Select-Object -First 3 | ForEach-Object { "{0} :: {1}" -f $_.Filename, $_.Line.Substring(0, [math]::Min(220, $_.Line.Length)) }
}
Write-Output ""
Write-Output "=== ops out.log for social-register ==="
Get-ChildItem "C:\Users\Administrator\ops\*social*" | ForEach-Object { $_.FullName + "  " + $_.LastWriteTime }
Write-Output ""
Write-Output "=== 2225e1b8: assistant messages mentioning Discord (first 25) ==="
Select-String -Path "C:\Users\Administrator\.openclaw\agents\main\sessions\2225e1b8-8e74-4509-a75a-8b539d6c07a5.jsonl" -Pattern "Discord" | Select-Object -First 25 | ForEach-Object {
  $line = $_.Line
  $idx = $line.IndexOf('"role":"assistant"')
  if ($idx -lt 0) { $idx = $line.IndexOf('"role":"toolResult"') }
  if ($idx -ge 0) { $snippet = $line.Substring($idx, [math]::Min(400, $line.Length - $idx)) } else { $snippet = $line.Substring(0, [math]::Min(400, $line.Length)) }
  "{0}" -f $snippet
}
Write-Output ""
Write-Output "=== 2225e1b8: lines mentioning verification/验证/social@ ==="
Select-String -Path "C:\Users\Administrator\.openclaw\agents\main\sessions\2225e1b8-8e74-4509-a75a-8b539d6c07a5.jsonl" -Pattern "验证|verification|social@|signup|register" | Select-Object -First 20 | ForEach-Object {
  $line = $_.Line
  $idx = $line.IndexOf('"content"')
  if ($idx -ge 0) { $snippet = $line.Substring($idx, [math]::Min(350, $line.Length - $idx)) } else { $snippet = $line.Substring(0, [math]::Min(350, $line.Length)) }
  "{0}" -f $snippet
}
Write-Output ""
Write-Output "=== Feishu PM send result around 09:21-09:22 UTC ==="
Select-String -Path "C:\Users\Administrator\.openclaw\agents\main\sessions\2225e1b8-8e74-4509-a75a-8b539d6c07a5.jsonl" -Pattern "message" | Where-Object { $_.Line -match '2026-08-23T09:21' -and $_.Line -match 'toolResult|feishu|Feishu|notify|private' } | Select-Object -First 8 | ForEach-Object {
  $line = $_.Line
  $ts = ""
  $m = [regex]::Match($line, '"timestamp":"([^"]+)"')
  if ($m.Success) { $ts = $m.Groups[1].Value }
  $idx = $line.IndexOf('"content"')
  if ($idx -ge 0) { $snippet = $line.Substring($idx, [math]::Min(700, $line.Length - $idx)) } else { $snippet = $line.Substring(0, [math]::Min(700, $line.Length)) }
  "{0} :: {1}" -f $ts, $snippet
}
Write-Output ""
Write-Output "=== 04 memory 2026-08-23.md: social section ==="
$mem = Get-Content "C:\Users\Administrator\.openclaw\workspace\memory\2026-08-23.md" -Encoding UTF8 -ErrorAction SilentlyContinue
$idx = ($mem | Select-String -Pattern "社媒账号注册" | Select-Object -First 1).LineNumber
if (-not $idx) { $idx = ($mem | Select-String -Pattern "Discord" | Select-Object -First 1).LineNumber }
if ($idx) { $mem[($idx-1)..([math]::Min($idx+15, $mem.Count-1))] } else { "no match" }
Write-Output "DONE"
