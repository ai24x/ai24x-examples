# 04 营销攻坚执行脚本（绕过 openclaw，SSH 直驱）
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\ops\_exec_mkt.ps1
$ErrorActionPreference = "Continue"
$logFile = "C:\Users\Administrator\ops\_exec_mkt.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Log($m) { "$ts $m" | Out-File $logFile -Encoding UTF8 -Append; Write-Host $m }

Log "=== 营销攻坚执行开始 ==="

# ===== 1. GitHub 推送示例代码 =====
Log "--- 任务1: GitHub 推送 ---"
$ghDir = "C:\ai24x01\p\deliverables-20260911"
if (Test-Path "$ghDir\README.md") {
    Log "交付物存在，开始推送..."
    # 尝试 git 方式推送到 ai24x/ai24x-examples
    $tmpDir = "C:\Users\Administrator\ops\_gh_temp"
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue }
    git clone "https://github.com/ai24x/ai24x-examples.git" $tmpDir 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Copy-Item "$ghDir\README.md" "$tmpDir\README.md" -Force
        Copy-Item "$ghDir\python\README.md" "$tmpDir\python\README.md" -Force
        Copy-Item "$ghDir\node\README.md" "$tmpDir\node\README.md" -Force
        Copy-Item "$ghDir\curl\README.md" "$tmpDir\curl\README.md" -Force
        cd $tmpDir
        git add -A
        git commit -m "feat: add Python/Node/curl examples [skip ci]" 2>&1 | Out-Null
        git push 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Log "✅ GitHub 推送成功" } else { Log "⚠️ GitHub 推送失败（可能需要 token）" }
        cd C:\
        Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
    } else {
        Log "⚠️ GitHub clone 失败（可能需要 token 或浏览器操作）"
    }
} else {
    Log "⚠️ 交付物目录不存在"
}

# ===== 2. dev.to 发布 =====
Log "--- 任务2: dev.to 发布 ---"
Log "⚠️ dev.to 需要浏览器登录 social@ai24x.com 手动发布"
Log "   文案路径: C:\ai24x01\p\deliverables-20260911\devto-deepseek-guide.md"

# ===== 3. D1 核验 =====
Log "--- 任务3: D1 核验 ---"
$receiptDir = "C:\Users\Administrator\ops\receipts\2026-09-11"
New-Item -ItemType Directory -Force -Path $receiptDir | Out-Null

$report = @"
# D1 核验回执 · 2026-09-11

## 账号状态
- X @ai24xapp: 待核验（需浏览器登录）
- GitHub @ai24x: 仓库 https://github.com/ai24x/ai24x-examples 已存在
- Reddit u/AI24X: 待核验
- dev.to: 待核验（需 social@ai24x.com 登录）
- HF: 待核验

## 发布权限
- www: git pull + restart AI24X-core
- open: git pull + restart AI24X-open-api
- HF: 待核验 Org 状态

## 分析工具
- GSC: 需雷总解锁

## 阻塞项
- GitHub push 需 token 或浏览器操作
- dev.to/HF/Reddit 需浏览器登录验证
- GSC 权限未解锁
"@

$report | Out-File "$receiptDir\receipt-20260911-04.md" -Encoding UTF8
Log "✅ D1 核验回执已落盘"

Log "=== 执行完成 ==="
Log "注意：GitHub/dev.to 需要浏览器手动操作，请登录 04 VPS 浏览器处理"
