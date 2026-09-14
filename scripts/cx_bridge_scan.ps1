param([string]$Dir)
Get-ChildItem -Path $Dir -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' } | Select-Object -ExpandProperty FullName
