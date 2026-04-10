# AI24X网站服务器 - Windows服务安装脚本
# PowerShell管理员权限运行

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   AI24X网站服务器 - Windows服务安装" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ 错误: 需要管理员权限运行此脚本" -ForegroundColor Red
    Write-Host "请以管理员身份运行PowerShell" -ForegroundColor Yellow
    pause
    exit 1
}

# 服务配置
$serviceName = "AI24XWebServer"
$serviceDisplayName = "AI24X网站服务器"
$serviceDescription = "AI24X网站系统 - 优化版服务器 (8GB内存专用)"
$workingDirectory = "C:\AI24X\OpenClaw\web\ai24x-website"
$nodePath = "C:\Program Files\nodejs\node.exe"
$scriptPath = "C:\AI24X\OpenClaw\web\ai24x-website\server-optimized.js"

# 检查Node.js
if (-not (Test-Path $nodePath)) {
    Write-Host "❌ 错误: Node.js未安装在默认位置" -ForegroundColor Red
    Write-Host "请检查Node.js安装路径: $nodePath" -ForegroundColor Yellow
    
    # 尝试在PATH中查找Node.js
    $nodeInPath = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeInPath) {
        $nodePath = $nodeInPath.Source
        Write-Host "✅ 在PATH中找到Node.js: $nodePath" -ForegroundColor Green
    } else {
        Write-Host "❌ 在PATH中未找到Node.js" -ForegroundColor Red
        pause
        exit 1
    }
}

# 检查服务器文件
if (-not (Test-Path $scriptPath)) {
    Write-Host "❌ 错误: 服务器文件不存在: $scriptPath" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "✅ 检查通过:" -ForegroundColor Green
Write-Host "   Node.js路径: $nodePath" -ForegroundColor Gray
Write-Host "   服务器文件: $scriptPath" -ForegroundColor Gray
Write-Host "   工作目录: $workingDirectory" -ForegroundColor Gray
Write-Host ""

# 检查服务是否已存在
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "⚠️ 服务 '$serviceName' 已存在" -ForegroundColor Yellow
    Write-Host "   状态: $($existingService.Status)" -ForegroundColor Gray
    Write-Host "   启动类型: $($existingService.StartType)" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "是否重新安装? (Y/N)"
    if ($choice -ne 'Y' -and $choice -ne 'y') {
        Write-Host "❌ 安装取消" -ForegroundColor Red
        pause
        exit 0
    }
    
    # 停止并删除现有服务
    Write-Host "🔄 停止现有服务..." -ForegroundColor Yellow
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    
    Write-Host "🗑️ 删除现有服务..." -ForegroundColor Yellow
    sc.exe delete $serviceName
    Start-Sleep -Seconds 2
}

# 创建服务
Write-Host "🚀 创建Windows服务..." -ForegroundColor Cyan

# 使用sc.exe创建服务
$scCommand = "sc.exe create $serviceName binPath= `"$nodePath --max-old-space-size=512 --expose-gc --nouse-idle-notification $scriptPath`" DisplayName= `"$serviceDisplayName`" start= auto"
Write-Host "   命令: $scCommand" -ForegroundColor Gray

# 执行创建命令
Invoke-Expression $scCommand

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 创建服务失败 (错误代码: $LASTEXITCODE)" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "✅ 服务创建成功" -ForegroundColor Green

# 配置服务
Write-Host "⚙️ 配置服务属性..." -ForegroundColor Cyan

# 设置描述
sc.exe description $serviceName "$serviceDescription"

# 设置工作目录
$regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName"
if (Test-Path $regPath) {
    Set-ItemProperty -Path $regPath -Name "ImagePath" -Value "`"$nodePath`" --max-old-space-size=512 --expose-gc --nouse-idle-notification `"$scriptPath`""
    
    # 添加工作目录
    New-ItemProperty -Path $regPath -Name "WorkingDirectory" -Value $workingDirectory -PropertyType String -Force | Out-Null
    
    # 配置恢复选项（崩溃后自动重启）
    $failureActions = @(
        @{Type = 1; Delay = 60000},   # 第一次失败: 60秒后重启
        @{Type = 1; Delay = 60000},   # 第二次失败: 60秒后重启  
        @{Type = 0; Delay = 0}        # 后续失败: 不操作
    )
    
    $failureActionsBytes = $failureActions | ForEach-Object {
        [byte[]]@($_.Type, 0, 0, 0) + [BitConverter]::GetBytes($_.Delay)
    }
    
    $failureActionsFlag = 1  # 启用失败操作
    $rebootMsg = ""
    $command = ""
    $actions = $failureActionsBytes
    
    $failureActionsValue = [byte[]]@($failureActionsFlag) + 
                          [byte[]]@(0,0,0) + 
                          [byte[]]@(0,0,0,0) + 
                          $actions + 
                          [System.Text.Encoding]::Unicode.GetBytes($rebootMsg + "`0") +
                          [System.Text.Encoding]::Unicode.GetBytes($command + "`0")
    
    New-ItemProperty -Path $regPath -Name "FailureActions" -Value $failureActionsValue -PropertyType Binary -Force | Out-Null
}

# 启动服务
Write-Host "🚀 启动服务..." -ForegroundColor Cyan
Start-Service -Name $serviceName

# 等待服务启动
Start-Sleep -Seconds 3

# 检查服务状态
$service = Get-Service -Name $serviceName
Write-Host ""
Write-Host "📊 服务状态:" -ForegroundColor Cyan
Write-Host "   名称: $($service.Name)" -ForegroundColor Gray
Write-Host "   显示名称: $($service.DisplayName)" -ForegroundColor Gray
Write-Host "   状态: $($service.Status)" -ForegroundColor Green
Write-Host "   启动类型: $($service.StartType)" -ForegroundColor Gray
Write-Host ""

# 测试服务
Write-Host "🔍 测试服务连接..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/health" -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ 服务测试成功: 健康检查正常" -ForegroundColor Green
        
        # 解析JSON响应
        $healthData = $response.Content | ConvertFrom-Json
        Write-Host "   🚀 服务器: $($healthData.server)" -ForegroundColor Gray
        Write-Host "   💾 内存: $($healthData.memory.rss)MB" -ForegroundColor Gray
        Write-Host "   📈 运行时间: $($healthData.uptime)秒" -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠️ 服务测试失败: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 AI24X网站服务器Windows服务安装完成!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 管理命令:" -ForegroundColor Cyan
Write-Host "   启动服务: Start-Service -Name $serviceName" -ForegroundColor Gray
Write-Host "   停止服务: Stop-Service -Name $serviceName" -ForegroundColor Gray
Write-Host "   重启服务: Restart-Service -Name $serviceName" -ForegroundColor Gray
Write-Host "   查看状态: Get-Service -Name $serviceName" -ForegroundColor Gray
Write-Host "   删除服务: sc.exe delete $serviceName" -ForegroundColor Gray
Write-Host ""
Write-Host "🌐 访问地址:" -ForegroundColor Cyan
Write-Host "   本地: http://localhost:3000" -ForegroundColor Gray
Write-Host "   公网: http://42.192.1.93:3000" -ForegroundColor Gray
Write-Host "   健康检查: http://localhost:3000/health" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 提示: 服务将在系统启动时自动运行" -ForegroundColor Yellow

pause