# AI24X网站服务监控脚本
# 自动检测和重启崩溃的服务

$ServiceName = "AI24X-Website"
$Port = 3000
$CheckInterval = 30  # 检查间隔（秒）
$MaxRestartAttempts = 3  # 最大重启尝试次数
$LogFile = "service-monitor.log"

# 日志函数
function Write-Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] $Message"
    Write-Host $LogMessage
    $LogMessage | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

# 检查服务是否运行
function Test-ServiceRunning {
    try {
        $Response = Invoke-WebRequest -Uri "http://localhost:$Port/health" -TimeoutSec 5 -ErrorAction Stop
        if ($Response.StatusCode -eq 200) {
            $HealthData = $Response.Content | ConvertFrom-Json
            return $true, $HealthData
        }
    } catch {
        return $false, $null
    }
    return $false, $null
}

# 启动服务
function Start-ServiceProcess {
    Write-Log "🚀 正在启动AI24X网站服务..."
    
    # 检查是否在正确的目录
    if (-not (Test-Path "package.json")) {
        Write-Log "❌ 错误：未找到package.json文件"
        return $false
    }
    
    # 安装依赖（如果需要）
    if (-not (Test-Path "node_modules")) {
        Write-Log "📦 正在安装依赖..."
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Log "❌ 依赖安装失败"
            return $false
        }
        Write-Log "✅ 依赖安装完成"
    }
    
    # 停止占用端口的进程
    $PortProcess = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
                   Where-Object {$_.State -eq "Listen"}
    
    if ($PortProcess) {
        Write-Log "⚠️  端口$Port已被占用，正在停止进程..."
        foreach ($Process in $PortProcess) {
            Stop-Process -Id $Process.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Log "✅ 已停止进程PID: $($Process.OwningProcess)"
        }
        Start-Sleep -Seconds 2
    }
    
    # 启动服务
    $env:NODE_ENV = "development"
    $env:PORT = $Port
    
    $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessInfo.FileName = "node"
    $ProcessInfo.Arguments = "server.js"
    $ProcessInfo.WorkingDirectory = $PWD.Path
    $ProcessInfo.RedirectStandardOutput = $true
    $ProcessInfo.RedirectStandardError = $true
    $ProcessInfo.UseShellExecute = $false
    $ProcessInfo.CreateNoWindow = $true
    
    $Process = New-Object System.Diagnostics.Process
    $Process.StartInfo = $ProcessInfo
    
    try {
        $Process.Start() | Out-Null
        Write-Log "✅ 服务进程已启动，PID: $($Process.Id)"
        
        # 等待服务启动
        Start-Sleep -Seconds 5
        
        # 检查服务是否成功启动
        $IsRunning, $HealthData = Test-ServiceRunning
        if ($IsRunning) {
            Write-Log "🎉 服务启动成功！"
            Write-Log "📊 健康状态: $($HealthData.status)"
            Write-Log "⏰ 运行时间: $($HealthData.timestamp)"
            return $true
        } else {
            Write-Log "❌ 服务启动后健康检查失败"
            $Process.Kill()
            return $false
        }
    } catch {
        Write-Log "❌ 启动服务时出错: $_"
        return $false
    }
}

# 主监控循环
Write-Log "========================================"
Write-Log "AI24X网站服务监控启动"
Write-Log "监控端口: $Port"
Write-Log "检查间隔: ${CheckInterval}秒"
Write-Log "========================================"

$RestartAttempts = 0

while ($true) {
    $IsRunning, $HealthData = Test-ServiceRunning
    
    if ($IsRunning) {
        if ($RestartAttempts -gt 0) {
            Write-Log "✅ 服务已恢复运行，重置重启计数器"
            $RestartAttempts = 0
        }
        
        # 记录健康状态（每小时记录一次）
        $CurrentMinute = (Get-Date).Minute
        if ($CurrentMinute -eq 0) {
            Write-Log "📊 服务运行正常 - Uptime: $([math]::Round($HealthData.uptime / 60))分钟"
        }
    } else {
        Write-Log "⚠️  服务未运行或健康检查失败"
        
        if ($RestartAttempts -lt $MaxRestartAttempts) {
            $RestartAttempts++
            Write-Log "🔄 尝试重启服务 ($RestartAttempts/$MaxRestartAttempts)..."
            
            if (Start-ServiceProcess) {
                Write-Log "✅ 服务重启成功"
                $RestartAttempts = 0
            } else {
                Write-Log "❌ 服务重启失败"
                
                # 如果连续失败，等待更长时间
                $WaitTime = $CheckInterval * $RestartAttempts
                Write-Log "⏳ 等待${WaitTime}秒后重试..."
                Start-Sleep -Seconds $WaitTime
            }
        } else {
            Write-Log "🚨 达到最大重启尝试次数($MaxRestartAttempts)，暂停监控"
            Write-Log "💡 请检查服务器日志或手动启动服务"
            
            # 等待一段时间后重置计数器
            Start-Sleep -Seconds 300  # 等待5分钟
            $RestartAttempts = 0
            Write-Log "🔄 重置重启计数器，继续监控..."
        }
    }
    
    Start-Sleep -Seconds $CheckInterval
}