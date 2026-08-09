$ErrorActionPreference = "SilentlyContinue"
$s = Get-ChildItem "C:\Users\Administrator\.openclaw\agents\main\sessions" -Filter "*.jsonl" | Where-Object { $_.Name -notmatch "trajectory|gateway" } | Sort-Object LastWriteTime -Descending | Select-Object -First 3
$s | ForEach-Object { Write-Output ("{0}  {1}  {2} bytes" -f $_.LastWriteTime, $_.Name, $_.Length) }
Write-Output "--- newest grep 9845592 ---"
if ($s) {
  $n = $s[0].FullName
  Select-String -Path $n -Pattern "9845592|task-04-deploy" -ErrorAction SilentlyContinue | Select-Object -First 3 | ForEach-Object { $_.Line.Substring(0, [Math]::Min(400, $_.Line.Length)) }
}
Write-Output "--- openclaw node procs ---"
Get-Process | Where-Object { $_.ProcessName -match "openclaw|node" } | Select-Object ProcessName, Id, StartTime | Format-Table -AutoSize | Out-String