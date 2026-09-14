param([string]$Dir)
Get-ChildItem -Path $Dir -File -Filter *.txt | Where-Object { $_.Name -notlike '_*' } | Sort-Object CreationTime | ForEach-Object { "{0:yyyy-MM-dd HH:mm:ss} | {1:yyyy-MM-dd HH:mm:ss} | {2}" -f $_.CreationTime, $_.LastWriteTime, $_.Name }
