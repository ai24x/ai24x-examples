# AI24X 推广自动化 · 司令启动检查
# 每次会话启动时自动执行
# 检查各副脑状态、催过期任务、推进下一步

param([switch]$Silent)

$ErrorActionPreference = "Continue"
$today = Get-Date -Format "yyyy-MM-dd"
$now = Get-Date -Format "HH:mm"

# ===== 01 检查 =====
function Check-01 {
    Write-Host "--- 01 状态 ---" -ForegroundColor Cyan
    $ok = ssh -o ConnectTimeout=8 -o BatchMode=yes Administrator@42.192.1.93 "echo OK" 2>$null
    if ($ok -ne "OK") { return "SSH_FAIL" }
    
    # 查回执
    $r = ssh -o ConnectTimeout=8 Administrator@42.192.1.93 "cmd /c dir C:\Users\Administrator\ops\receipts\$today\ 2>nul" 2>$null
    $hasReceipt = $r -match "receipt"
    
    # 查最新 session
    $s = ssh -o ConnectTimeout=8 Administrator@42.192.1.93 "cmd /c dir /tw /b /o-d C:\Users\Administrator\.openclaw\agents\main\sessions\*.jsonl 2>nul | findstr /v trajectory" 2>$null
    $sessions = ($s -split "`n").Count
    
    return @{status="OK"; receipt=$hasReceipt; sessions=$sessions}
}

# ===== 04 检查 =====
function Check-04 {
    Write-Host "--- 04 状态 ---" -ForegroundColor Cyan
    $ok = ssh -o ConnectTimeout=8 -o BatchMode=yes Administrator@43.160.246.30 "echo OK" 2>$null
    if ($ok -ne "OK") { return "SSH_FAIL" }
    
    $r = ssh -o ConnectTimeout=8 Administrator@43.160.246.30 "cmd /c dir C:\Users\Administrator\ops\receipts\$today\ 2>nul" 2>$null
    $hasReceipt = $r -match "receipt"
    
    return @{status="OK"; receipt=$hasReceipt}
}

# ===== 指挥官检查 =====
function Check-Commander {
    Write-Host "--- 指挥官状态 ---" -ForegroundColor Cyan
    $replies = Get-ChildItem "E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\回复" | Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-12) }
    return @{recentReply=($replies.Count -gt 0); replyCount=$replies.Count}
}

# ===== 自动催办 =====
function Auto-Nudge {
    param([string]$Target, [string]$Reason)
    Write-Host "⚠️ 自动催办 $Target ：$Reason" -ForegroundColor Yellow
    # 写催办文件到对应收发目录
    $nudgeFile = "E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\指令\auto-nudge-$today-$Target.md"
    @"
# 自动催办 · $Target · $today
> 原因：$Reason
> 本催办由自动化框架自动生成

请确认任务状态并回执。
"@ | Out-File $nudgeFile -Encoding UTF8
}

# ===== 主流程 =====
Write-Host "`n========== AI24X 推广自动化检查 $today $now ==========" -ForegroundColor Green

$r1 = Check-01
$r4 = Check-04
$rc = Check-Commander

# 汇总
Write-Host "`n=== 汇总 ===" -ForegroundColor Green
if ($r1 -eq "SSH_FAIL") { Write-Host "🔴 01 SSH 不通" -ForegroundColor Red }
else { Write-Host "🟢 01 在线 | 回执:$($r1.receipt) | 会话:$($r1.sessions)" }

if ($r4 -eq "SSH_FAIL") { Write-Host "🔴 04 SSH 不通" -ForegroundColor Red }
else { Write-Host "🟢 04 在线 | 回执:$($r4.receipt)" }

Write-Host "🟡 指挥官最近12h回复:$($rc.replyCount)"

# 自动催办逻辑
if ($r1 -ne "SSH_FAIL" -and -not $r1.receipt) {
    # 01 无回执超过24h才催
    $lastTask = Get-ChildItem "E:\AI24X\ai24x-website\ai24x01\docs\营销\收发\指令" -Filter "*01*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($lastTask -and $lastTask.LastWriteTime -lt (Get-Date).AddHours(-12)) {
        Auto-Nudge -Target "01" -Reason "任务 $($lastTask.Name) 已超过12h无回执"
    }
}

Write-Host "========== 检查完成 ==========`n" -ForegroundColor Green

# 输出状态摘要（给用户看）
$summary = @"
🌅 **AI24X 推广晨报 · $today**

**01** $($r1 -eq "SSH_FAIL" ? "🔴 不通" : "🟢 在线")
**04** $($r4 -eq "SSH_FAIL" ? "🔴 不通" : "🟢 在线")
**指挥官** 最近12h回复: $($rc.replyCount) 条

**今日待办：**
- 等 01 回执（GitHub/dev.to/需求）
- 等 04 发布核验
- 等指挥官确认接手
"@

if (-not $Silent) { Write-Host $summary }
