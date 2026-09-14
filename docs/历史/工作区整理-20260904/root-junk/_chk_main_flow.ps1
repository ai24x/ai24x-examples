
$OutputEncoding=[Console]::OutputEncoding=[Text.Encoding]::UTF8
Write-Output "=== main.py 425-560 (chat entry + auth flow) ==="
Get-Content C:\ai24x01\api\main.py | Select-Object -Skip 420 -First 150