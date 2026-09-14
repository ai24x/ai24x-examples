$ErrorActionPreference = "SilentlyContinue"
Get-ChildItem "C:\Users\Administrator\ops\*" | Sort-Object LastWriteTime -Descending | Select-Object Name, Length, LastWriteTime | Out-File -FilePath "C:\Users\Administrator\ops\_ls.txt" -Encoding UTF8
Get-Content "C:\Users\Administrator\ops\_ls.txt" -Encoding UTF8
