$ErrorActionPreference = "SilentlyContinue"
Write-Output "--- 监听端口 (core 相关) ---"
netstat -ano | Select-String "LISTENING" | Select-String ":8000|:8002|:80 " | Select-Object -First 10 | ForEach-Object { $_.Line.Trim() }
Write-Output "--- 8000/8002 health ---"
foreach ($port in 8000, 8002) { try { $h = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $port + "/health") -TimeoutSec 8; Write-Output ("port=" + $port + " status=" + $h.status + " commit=" + $h.commit) } catch { Write-Output ("port=" + $port + " ERR") } }
Write-Output "--- nginx / web 站点目录修改时间 ---"
if (Test-Path C:\ai24x01\web\index.html) { (Get-Item C:\ai24x01\web\index.html).LastWriteTime; Select-String -Path C:\ai24x01\web\index.html -Pattern "tag tag-value" -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Line.Trim().Substring(0, [Math]::Min(150, $_.Line.Trim().Length)) } }
if (Test-Path C:\ai24x01\web\product.html) { Select-String -Path C:\ai24x01\web\product.html -Pattern "matrix.vip|名模清单" -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.Line.Trim().Substring(0, [Math]::Min(150, $_.Line.Trim().Length)) } }
Write-Output "--- 最近两个会话文件 mtime ---"
Get-ChildItem "C:\Users\Administrator\.openclaw\agents\main\sessions" -Filter "*.jsonl" | Where-Object { $_.Name -notmatch "trajectory|gateway" } | Sort-Object LastWriteTime -Descending | Select-Object -First 2 | ForEach-Object { Write-Output ($_.LastWriteTime.ToString("HH:mm:ss") + "  " + $_.Name + "  " + $_.Length + "B") }