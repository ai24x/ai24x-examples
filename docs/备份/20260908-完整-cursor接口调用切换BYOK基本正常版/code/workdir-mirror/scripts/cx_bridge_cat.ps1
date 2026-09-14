param([string]$Dir)
Get-ChildItem -Path $Dir -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' } | Sort-Object Name | ForEach-Object {
  Write-Output ("========== " + $_.Name + " (" + $_.Length + " bytes) ==========")
  Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
  Write-Output ""
}
