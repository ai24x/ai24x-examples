# AI24X 推广自动化监控脚本
# 用途：每天检查各副脑任务回执，汇总状态，超时自动催办
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File scripts\promo-automation.ps1

$ErrorActionPreference = "Continue"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$today = Get-Date -Format "yyyy-MM-dd"
$logDir = "E:\AI24X\ai24x-website\ai24x01\ops\promo-automation"
$logFile = "$logDir\$today.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Log($m) { "$(Get-Date -Format 'HH:mm:ss') $m" | Out-File $logFile -Encoding UTF8 -Append }

Log "=== 推广自动化监控 $today ==="

# ---- 1. 检查 01 回执 ----
Log "--- 检查 01 回执 ---"
$ssh01 = "Administrator@42.192.1.93"
$receipt01 = ssh -o ConnectTimeout=8 $ssh01 "cmd /c dir C:\Users\Administrator\ops\receipts\$today\ 2>nul" 2>$null
if ($receipt01 -match "receipt") {
    Log "✅ 01 今日回执已落盘"
} else {
    Log "⚠️ 01 今日无回执"
}

# ---- 2. 检查 04 回执 ----
Log "--- 检查 04 回执 ---"
$ssh04 = "Administrator@43.160.246.30"
$receipt04 = ssh -o ConnectTimeout=8 $ssh04 "cmd /c dir C:\Users\Administrator\ops\receipts\$today\ 2>nul" 2>$null
if ($receipt04 -match "receipt") {
    Log "✅ 04 今日回执已落盘"
} else {
    Log "⚠️ 04 今日无回执"
}

# ---- 3. 检查指挥官回执 ----
$cmdReply = Get-ChildItem "E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\回复" | Where-Object { $_.LastWriteTime -gt [DateTime]"$today 00:00" }
if ($cmdReply) {
    Log "✅ 指挥官有回复"
} else {
    Log "⚠️ 指挥官今日无回复"
}

# ---- 4. 检查 01 任务超时（>24h 无回执） ----
$taskFiles = Get-ChildItem "E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\指令" -Filter "*01*" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-24) }
if ($taskFiles) {
    Log "⚠️ 以下 01 任务超时 24h+："
    $taskFiles | ForEach-Object { Log "   $($_.Name) ($($_.LastWriteTime))" }
}

# ---- 5. 汇总 ----
Log "=== 监控完成 ==="
Log ""
