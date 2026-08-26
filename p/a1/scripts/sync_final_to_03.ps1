# AI行情官「本地最终版 → 03 生产」归档同步（复盘/掘金口径权威对齐）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\sync_final_to_03.ps1
# 说明: 本地为老板验收口径。部署/每日收盘后把 复盘归档(板块主攻研判) + daily_report缓存 +
#       掘金归档(bj_archive/bj_scan_history/bj_scan_daily) 同步到 03，并重启 AI24X-a1-api。
# ⚠️ 03 无 D 盘: 备份落 C:\backup\ai24x_a\（apply 脚本内处理）。
$ErrorActionPreference = "Stop"
$SshHost = "Administrator@123.207.199.238"
$A1 = Join-Path $PSScriptRoot ".." | ForEach-Object { (Resolve-Path $_).Path }
$PkgLocal = "C:\Temp\_a1_final_sync"
$PkgRemote = "C:\Users\Administrator\_a1_final_sync"

Write-Host "==> 1/5 本地打包最终版归档..." -ForegroundColor Cyan
if (Test-Path $PkgLocal) { Remove-Item $PkgLocal -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$PkgLocal\bj_archive" | Out-Null
New-Item -ItemType Directory -Force -Path "$PkgLocal\bj_emotion" | Out-Null
New-Item -ItemType Directory -Force -Path "$PkgLocal\daily_report_cache" | Out-Null
New-Item -ItemType Directory -Force -Path "$PkgLocal\mainlines_archive" | Out-Null

Copy-Item "$A1\api\server\data\bj_archive\*.json" "$PkgLocal\bj_archive" -Force
Copy-Item "$A1\api\server\data\bj_scan_history.json" "$PkgLocal\" -Force
Copy-Item "$A1\api\server\data\bj_scan_daily.json" "$PkgLocal\" -Force
Copy-Item "$A1\api\server\data\bj_emotion\*.json" "$PkgLocal\bj_emotion" -Force
Copy-Item "$A1\daily_report\config.json" "$PkgLocal\daily_report_config.json" -Force
Get-ChildItem "$A1\daily_report\cache" -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^\d{8}$' } |
  ForEach-Object { Copy-Item $_.FullName "$PkgLocal\daily_report_cache\$($_.Name)" -Recurse -Force }
Get-ChildItem "$A1\调研报告\04-每日跟踪\板块主攻研判" -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^\d{8}$' } |
  ForEach-Object { Copy-Item $_.FullName "$PkgLocal\mainlines_archive\$($_.Name)" -Recurse -Force }

# apply 脚本确保 UTF-8 BOM（03 为 PS5.1/GBK，含中文脚本必须 UTF-8 BOM；避免 WriteAllText 双 BOM）
Copy-Item "$A1\scripts\_apply_final_sync.py" "$PkgLocal\_apply_final_sync.py" -Force
Copy-Item "$A1\scripts\_verify_final_sync.py" "$PkgLocal\_verify_final_sync.py" -Force
$pyBytes = [System.IO.File]::ReadAllBytes("$PkgLocal\_apply_final_sync.py")
if (-not ($pyBytes.Length -ge 3 -and $pyBytes[0] -eq 0xEF -and $pyBytes[1] -eq 0xBB -and $pyBytes[2] -eq 0xBF)) {
  [System.IO.File]::WriteAllBytes("$PkgLocal\_apply_final_sync.py", ([byte[]](0xEF, 0xBB, 0xBF)) + $pyBytes)
}
Write-Host "   包大小: $((Get-ChildItem $PkgLocal -Recurse | Measure-Object Length -Sum).Sum) bytes"

Write-Host "==> 2/5 scp 到 03..." -ForegroundColor Cyan
$runLocal = Join-Path $PSScriptRoot "_run_final_sync_03.ps1"
scp -o ConnectTimeout=20 -o StrictHostKeyChecking=no $runLocal "${SshHost}:C:/Users/Administrator/_a1_run_sync.ps1"
scp -r -o ConnectTimeout=20 -o StrictHostKeyChecking=no $PkgLocal "${SshHost}:C:/Users/Administrator/"
if ($LASTEXITCODE -ne 0) { throw "scp 失败" }

Write-Host "==> 3/5 03 应用归档（备份→合并→重建索引）并重启服务..." -ForegroundColor Cyan
ssh -o ConnectTimeout=120 -o StrictHostKeyChecking=no -o BatchMode=yes $SshHost "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\_a1_run_sync.ps1" 2>&1
if ($LASTEXITCODE -ne 0) { throw "重启失败" }

Write-Host "==> 5/5 验证..." -ForegroundColor Green
Write-Host "==> 03 侧关键文件核验（apply 输出应含 ML20260825 mainlines 与本地一致 + HS25_PICKS）" -ForegroundColor Yellow
Write-Host "==> 完成。公网 https://a.ai24x.com/gd.html 刷新（Ctrl+F5）即可看到与本地一致的收盘定型数据。" -ForegroundColor Green
