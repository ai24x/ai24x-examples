# AI24X网站服务 - Windows服务配置脚本
# 创建时间: 2026-03-20
# 功能: 将AI24X网站配置为Windows服务，实现永久在线

# 配置参数
$ServiceName = "AI24XWebsiteService"
$ServiceDisplayName = "AI24X网站服务"
$ServiceDescription = "AI24X智能体系统网站服务，提供AI工具库和教程内容"
$NodePath = "C:\Program Files\nodejs\node.exe"
$ScriptPath = "C:\AI24X\OpenClaw\web\ai24x-website\server-clean-fixed.js"
$WorkingDirectory = "C:\AI24X\OpenClaw\web\ai24x-website"
$LogPath = "C:\AI24X\OpenClaw\web\ai24x-website\service.log"

Write-Host "=========================================="
Write-Host "AI24X网站服务 - Windows服务配置"
Write-Host "=========================================="
Write-Host ""

# 检查Node.js
if (-not (Test-Path $NodePath)) {
    Write-Host "❌ 找不到Node.js，请先安装Node.js" -ForegroundColor Red
    Write-Host "下载地址: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# 检查脚本文件
if (-not (Test-Path $ScriptPath)) {
    Write-Host "❌ 找不到服务器脚本: $ScriptPath" -ForegroundColor Red
    exit 1
}

# 检查工作目录
if (-not (Test-Path $WorkingDirectory)) {
    Write-Host "❌ 找不到工作目录: $WorkingDirectory" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 环境检查通过" -ForegroundColor Green
Write-Host ""

# 选择操作
Write-Host "请选择操作:" -ForegroundColor Cyan
Write-Host "1. 安装为Windows服务（自动启动）"
Write-Host "2. 卸载Windows服务"
Write-Host "3. 启动服务"
Write-Host "4. 停止服务"
Write-Host "5. 查看服务状态"
Write-Host "6. 手动启动（不安装服务）"
Write-Host ""

$choice = Read-Host "请输入选择 (1-6)"

switch ($choice) {
    "1" {
        # 安装为Windows服务
        Write-Host "正在安装Windows服务..." -ForegroundColor Yellow
        
        # 检查是否已安装
        $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($existingService) {
            Write-Host "⚠️ 服务已存在，先停止并删除..." -ForegroundColor Yellow
            Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
            sc.exe delete $ServiceName
            Start-Sleep -Seconds 2
        }
        
        # 创建服务
        $serviceArgs = "`"$NodePath`" `"$ScriptPath`""
        
        Write-Host "创建服务参数: $serviceArgs" -ForegroundColor Gray
        
        # 使用sc.exe创建服务
        $result = sc.exe create $ServiceName `
            binPath= "$NodePath $ScriptPath" `
            DisplayName= "$ServiceDisplayName" `
            start= "auto" `
            obj= "LocalSystem" `
            depend= "Tcpip/Dhcp"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ 服务创建成功" -ForegroundColor Green
            
            # 设置服务描述
            sc.exe description $ServiceName "$ServiceDescription"
            
            # 启动服务
            Start-Service -Name $ServiceName
            Write-Host "✅ 服务已启动" -ForegroundColor Green
            
            # 验证服务状态
            Start-Sleep -Seconds 3
            $serviceStatus = Get-Service -Name $ServiceName
            Write-Host "服务状态: $($serviceStatus.Status)" -ForegroundColor Cyan
            Write-Host "启动类型: $($serviceStatus.StartType)" -ForegroundColor Cyan
            
            # 测试访问
            Write-Host "测试网站访问..." -ForegroundColor Yellow
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5
                Write-Host "✅ 网站访问成功 (状态码: $($response.StatusCode))" -ForegroundColor Green
            } catch {
                Write-Host "⚠️ 网站访问测试失败: $_" -ForegroundColor Yellow
            }
            
            Write-Host ""
            Write-Host "=========================================="
            Write-Host "✅ AI24X网站服务已配置为Windows服务" -ForegroundColor Green
            Write-Host "服务名称: $ServiceName" -ForegroundColor Cyan
            Write-Host "显示名称: $ServiceDisplayName" -ForegroundColor Cyan
            Write-Host "启动类型: 自动" -ForegroundColor Cyan
            Write-Host "访问地址: http://localhost:3000" -ForegroundColor Cyan
            Write-Host "=========================================="
            
        } else {
            Write-Host "❌ 服务创建失败" -ForegroundColor Red
            Write-Host "错误代码: $LASTEXITCODE" -ForegroundColor Red
            Write-Host "建议使用管理员权限运行此脚本" -ForegroundColor Yellow
        }
    }
    
    "2" {
        # 卸载服务
        Write-Host "正在卸载Windows服务..." -ForegroundColor Yellow
        
        $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($existingService) {
            # 停止服务
            Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            
            # 删除服务
            sc.exe delete $ServiceName
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ 服务卸载成功" -ForegroundColor Green
            } else {
                Write-Host "❌ 服务卸载失败" -ForegroundColor Red
            }
        } else {
            Write-Host "⚠️ 服务不存在" -ForegroundColor Yellow
        }
    }
    
    "3" {
        # 启动服务
        Write-Host "正在启动服务..." -ForegroundColor Yellow
        
        $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($existingService) {
            Start-Service -Name $ServiceName
            Write-Host "✅ 服务已启动" -ForegroundColor Green
            
            # 验证状态
            Start-Sleep -Seconds 2
            $serviceStatus = Get-Service -Name $ServiceName
            Write-Host "服务状态: $($serviceStatus.Status)" -ForegroundColor Cyan
        } else {
            Write-Host "❌ 服务不存在，请先安装" -ForegroundColor Red
        }
    }
    
    "4" {
        # 停止服务
        Write-Host "正在停止服务..." -ForegroundColor Yellow
        
        $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($existingService) {
            Stop-Service -Name $ServiceName -Force
            Write-Host "✅ 服务已停止" -ForegroundColor Green
        } else {
            Write-Host "❌ 服务不存在" -ForegroundColor Red
        }
    }
    
    "5" {
        # 查看服务状态
        Write-Host "服务状态检查..." -ForegroundColor Yellow
        
        $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($existingService) {
            Write-Host "服务名称: $($existingService.Name)" -ForegroundColor Cyan
            Write-Host "显示名称: $($existingService.DisplayName)" -ForegroundColor Cyan
            Write-Host "状态: $($existingService.Status)" -ForegroundColor Cyan
            Write-Host "启动类型: $($existingService.StartType)" -ForegroundColor Cyan
            
            # 测试网站访问
            Write-Host "测试网站访问..." -ForegroundColor Yellow
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5
                Write-Host "✅ 网站访问成功 (状态码: $($response.StatusCode))" -ForegroundColor Green
            } catch {
                Write-Host "❌ 网站访问失败: $_" -ForegroundColor Red
            }
        } else {
            Write-Host "❌ 服务不存在" -ForegroundColor Red
        }
    }
    
    "6" {
        # 手动启动
        Write-Host "正在手动启动网站服务..." -ForegroundColor Yellow
        
        # 停止可能存在的进程
        taskkill /f /im node.exe 2>$null
        Start-Sleep -Seconds 2
        
        # 启动服务
        Set-Location $WorkingDirectory
        Start-Process -FilePath $NodePath -ArgumentList $ScriptPath -WindowStyle Hidden
        
        Write-Host "✅ 网站服务已启动" -ForegroundColor Green
        Write-Host "进程将在后台运行" -ForegroundColor Cyan
        Write-Host "访问地址: http://localhost:3000" -ForegroundColor Cyan
        
        # 测试访问
        Start-Sleep -Seconds 3
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 5
            Write-Host "✅ 网站访问测试成功" -ForegroundColor Green
        } catch {
            Write-Host "⚠️ 网站访问测试失败: $_" -ForegroundColor Yellow
        }
    }
    
    default {
        Write-Host "❌ 无效的选择" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")