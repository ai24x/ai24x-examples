$dir = 'E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\回复\'
Get-ChildItem -Path $dir -File -Filter *.txt | Where-Object { -not $_.Name.StartsWith('_') } | Select-Object -ExpandProperty FullName
