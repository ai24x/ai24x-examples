# AI24X 副脑03 · OpenClaw 急救升级脚本
# 复制全部 → 粘贴到 PowerShell 回车执行

Write-Host "=== 1/6 杀掉卡死进程 ===" -ForegroundColor Cyan
taskkill /F /IM node.exe 2>$null
Start-Sleep 1

Write-Host "=== 2/6 检查 Node.js 版本 ===" -ForegroundColor Cyan
node --version

Write-Host "=== 3/6 安装 OpenClaw 最新版 ===" -ForegroundColor Cyan
npm install -g openclaw@latest

Write-Host "=== 4/6 验证版本 ===" -ForegroundColor Cyan
openclaw --version

Write-Host "=== 5/6 重启 Gateway ===" -ForegroundColor Cyan
openclaw gateway restart

Write-Host "=== 6/6 检查健康 ===" -ForegroundColor Cyan
Start-Sleep 3
openclaw health

Write-Host "=== 完成！装好后通知主脑统一配飞书 ===" -ForegroundColor Green
