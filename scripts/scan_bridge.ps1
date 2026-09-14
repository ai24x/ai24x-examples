$dirs = @(
  'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\指令',
  'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\回复'
)
foreach ($d in $dirs) {
  Write-Output "=== $d ==="
  if (Test-Path $d) {
    Get-ChildItem -Path $d -File -Filter *.txt | Where-Object { -not $_.Name.StartsWith('_') } | ForEach-Object { Write-Output $_.FullName }
  } else {
    Write-Output "(DIR NOT FOUND)"
  }
}
