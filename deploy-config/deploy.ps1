# AI24X网站自动化部署脚本 (PowerShell)
# 版本: 1.0.0
# 作者: 副脑01 (首席开发工程师)
# 日期: 2026-03-18

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("preprod", "production", "staging")]
    [string]$Environment = "preprod",
    
    [Parameter(Mandatory=$false)]
    [string]$Branch = "develop",
    
    [Parameter(Mandatory=$false)]
    [switch]$Force = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$Rollback = $false,
    
    [Parameter(Mandatory=$false)]
    [int]$RollbackVersion = 1
)

# ========== 配置变量 ==========
$ScriptVersion = "1.0.0"
$StartTime = Get-Date
$LogFile = "deploy-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$ProjectRoot = $PSScriptRoot
$AppName = "ai24x-website-$Environment"
$BackupDir = "$ProjectRoot\backups"
$ErrorActionPreference = "Stop"

# ========== 颜色定义 ==========
$ColorGreen = "Green"
$ColorRed = "Red"
$ColorYellow = "Yellow"
$ColorCyan = "Cyan"
$ColorMagenta = "Magenta"

# ========== 日志函数 ==========
function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$Color = "White"
    )
    
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    
    Write-Host $LogMessage -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $LogMessage
}

function Write-Success {
    param([string]$Message)
    Write-Log -Message $Message -Level "SUCCESS" -Color $ColorGreen
}

function Write-Error {
    param([string]$Message)
    Write-Log -Message $Message -Level "ERROR" -Color $ColorRed
    throw $Message
}

function Write-Warning {
    param([string]$Message)
    Write-Log -Message $Message -Level "WARNING" -Color $ColorYellow
}

function Write-Info {
    param([string]$Message)
    Write-Log -Message $Message -Level "INFO" -Color $ColorCyan
}

# ========== 环境检查 ==========
function Test-Environment {
    Write-Info "检查部署环境..."
    
    # 检查Node.js
    $NodeVersion = node --version
    if (-not $NodeVersion) {
        Write-Error "Node.js未安装，请先安装Node.js 18+"
    }
    Write-Info "Node.js版本: $NodeVersion"
    
    # 检查npm
    $NpmVersion = npm --version
    Write-Info "npm版本: $NpmVersion"
    
    # 检查Git
    $GitVersion = git --version
    if (-not $GitVersion) {
        Write-Error "Git未安装，请先安装Git"
    }
    Write-Info "Git版本: $GitVersion"
    
    # 检查PM2
    $Pm2Version = pm2 --version 2>$null
    if (-not $Pm2Version) {
        Write-Warning "PM2未安装，将尝试安装..."
        npm install -g pm2
    }
    Write-Info "PM2版本: $Pm2Version"
    
    # 检查端口占用
    $PortInUse = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    if ($PortInUse) {
        Write-Warning "端口3000已被占用，PID: $($PortInUse.OwningProcess)"
        if (-not $Force) {
            Write-Error "使用 -Force 参数强制停止占用进程"
        }
        Stop-Process -Id $PortInUse.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    
    Write-Success "环境检查通过"
}

# ========== 备份函数 ==========
function Backup-Current {
    Write-Info "备份当前版本..."
    
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }
    
    $BackupName = "backup-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $BackupPath = "$BackupDir\$BackupName.zip"
    
    # 备份数据目录
    if (Test-Path "$ProjectRoot\data") {
        Compress-Archive -Path "$ProjectRoot\data\*" -DestinationPath $BackupPath -Force
        Write-Info "数据备份完成: $BackupPath"
    }
    
    # 备份配置文件
    if (Test-Path "$ProjectRoot\.env") {
        Copy-Item "$ProjectRoot\.env" "$BackupDir\.env.$BackupName.backup" -Force
    }
    
    Write-Success "备份完成"
    return $BackupName
}

# ========== 代码更新 ==========
function Update-Code {
    param([string]$Branch)
    
    Write-Info "更新代码，分支: $Branch"
    
    # 检查Git仓库
    if (-not (Test-Path "$ProjectRoot\.git")) {
        Write-Error "当前目录不是Git仓库"
    }
    
    # 拉取最新代码
    try {
        git fetch origin
        git checkout $Branch
        git pull origin $Branch
        Write-Success "代码更新完成"
    }
    catch {
        Write-Error "代码更新失败: $_"
    }
    
    # 显示最新提交
    $LatestCommit = git log --oneline -1
    Write-Info "最新提交: $LatestCommit"
}

# ========== 依赖安装 ==========
function Install-Dependencies {
    Write-Info "安装依赖..."
    
    # 检查package.json
    if (-not (Test-Path "$ProjectRoot\package.json")) {
        Write-Error "package.json文件不存在"
    }
    
    # 安装依赖
    try {
        if ($Environment -eq "production") {
            npm ci --only=production
        } else {
            npm install
        }
        Write-Success "依赖安装完成"
    }
    catch {
        Write-Error "依赖安装失败: $_"
    }
}

# ========== 环境配置 ==========
function Configure-Environment {
    Write-Info "配置环境..."
    
    # 检查环境配置文件
    $EnvExample = "$ProjectRoot\.env.example"
    $EnvFile = "$ProjectRoot\.env"
    
    if (-not (Test-Path $EnvExample)) {
        Write-Warning "环境模板文件不存在: $EnvExample"
        return
    }
    
    if (-not (Test-Path $EnvFile)) {
        Write-Info "创建环境配置文件"
        Copy-Item $EnvExample $EnvFile
        Write-Warning "请编辑 $EnvFile 文件配置实际环境变量"
    } else {
        Write-Info "环境配置文件已存在"
    }
    
    # 加载环境变量
    if (Test-Path $EnvFile) {
        Get-Content $EnvFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)') {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim()
                [Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
}

# ========== 服务启动 ==========
function Start-Service {
    Write-Info "启动服务..."
    
    # 选择启动文件
    $ServerFile = if (Test-Path "$ProjectRoot\server-enhanced.js") {
        "server-enhanced.js"
    } else {
        "server.js"
    }
    
    Write-Info "使用服务器文件: $ServerFile"
    
    # 停止现有服务
    $ExistingProcess = pm2 list | Select-String $AppName
    if ($ExistingProcess) {
        Write-Info "停止现有服务: $AppName"
        pm2 stop $AppName
        pm2 delete $AppName
    }
    
    # 启动新服务
    try {
        pm2 start $ServerFile --name $AppName --env $Environment
        Write-Success "服务启动命令已发送"
        
        # 等待服务启动
        Write-Info "等待服务启动..."
        Start-Sleep -Seconds 5
        
        # 检查服务状态
        $ServiceStatus = pm2 show $AppName
        if ($ServiceStatus -match "online") {
            Write-Success "服务启动成功"
        } else {
            Write-Error "服务启动失败，请检查日志"
        }
    }
    catch {
        Write-Error "服务启动失败: $_"
    }
}

# ========== 健康检查 ==========
function Test-Health {
    Write-Info "执行健康检查..."
    
    $MaxRetries = 5
    $RetryCount = 0
    $HealthCheckUrl = "http://localhost:3000/health"
    
    while ($RetryCount -lt $MaxRetries) {
        try {
            $Response = Invoke-WebRequest -Uri $HealthCheckUrl -TimeoutSec 10 -ErrorAction Stop
            if ($Response.StatusCode -eq 200) {
                $HealthData = $Response.Content | ConvertFrom-Json
                Write-Success "健康检查通过: $($HealthData.status)"
                Write-Info "服务信息: $($HealthData | ConvertTo-Json -Compress)"
                return $true
            }
        }
        catch {
            Write-Warning "健康检查失败 (尝试 $($RetryCount+1)/$MaxRetries): $_"
            $RetryCount++
            if ($RetryCount -lt $MaxRetries) {
                Start-Sleep -Seconds 5
            }
        }
    }
    
    Write-Error "健康检查失败，服务可能未正确启动"
    return $false
}

# ========== 回滚函数 ==========
function Invoke-Rollback {
    param([int]$Version = 1)
    
    Write-Info "执行回滚到版本: $Version"
    
    # 查找备份文件
    $BackupFiles = Get-ChildItem $BackupDir -Filter "backup-$Environment-*.zip" | Sort-Object LastWriteTime -Descending
    if ($BackupFiles.Count -eq 0) {
        Write-Error "没有找到可用的备份文件"
    }
    
    if ($Version -gt $BackupFiles.Count) {
        Write-Error "版本 $Version 不存在，可用版本: 1-$($BackupFiles.Count)"
    }
    
    $BackupFile = $BackupFiles[$Version - 1]
    Write-Info "使用备份文件: $($BackupFile.Name)"
    
    # 停止服务
    pm2 stop $AppName 2>$null
    pm2 delete $AppName 2>$null
    
    # 恢复备份
    Expand-Archive -Path $BackupFile.FullName -DestinationPath "$ProjectRoot\data" -Force
    Write-Success "备份恢复完成"
    
    # 启动服务
    Start-Service
    Test-Health
    
    Write-Success "回滚完成"
}

# ========== 清理函数 ==========
function Cleanup-OldBackups {
    Write-Info "清理旧备份..."
    
    $BackupFiles = Get-ChildItem $BackupDir -Filter "backup-*.zip"
    if ($BackupFiles.Count -gt 10) {
        $FilesToDelete = $BackupFiles | Sort-Object LastWriteTime | Select-Object -First ($BackupFiles.Count - 10)
        $FilesToDelete | ForEach-Object {
            Remove-Item $_.FullName -Force
            Write-Info "删除旧备份: $($_.Name)"
        }
        Write-Success "清理完成，保留最近10个备份"
    } else {
        Write-Info "备份文件数量正常 ($($BackupFiles.Count)个)，无需清理"
    }
}

# ========== 主部署流程 ==========
function Start-Deployment {
    Write-Info "开始部署 - 环境: $Environment, 分支: $Branch"
    Write-Info "部署脚本版本: $ScriptVersion"
    Write-Info "开始时间: $StartTime"
    Write-Info "日志文件: $LogFile"
    
    try {
        # 1. 环境检查
        Test-Environment
        
        # 2. 备份当前版本
        $BackupName = Backup-Current
        
        # 3. 更新代码
        Update-Code -Branch $Branch
        
        # 4. 安装依赖
        Install-Dependencies
        
        # 5. 环境配置
        Configure-Environment
        
        # 6. 启动服务
        Start-Service
        
        # 7. 健康检查
        $HealthResult = Test-Health
        
        if ($HealthResult) {
            $EndTime = Get-Date
            $Duration = New-TimeSpan -Start $StartTime -End $EndTime
            Write-Success "部署成功完成!"
            Write-Info "部署用时: $($Duration.TotalSeconds.ToString('0.00'))秒"
            Write-Info "备份名称: $BackupName"
            Write-Info "完成时间: $EndTime"
            
            # 8. 清理旧备份
            Cleanup-OldBackups
            
            return $true
        } else {
            Write-Error "健康检查失败，部署未完成"
        }
    }
    catch {
        Write-Error "部署过程中出现错误: $_"
        Write-Warning "建议执行回滚: .\deploy.ps1 -Environment $Environment -Rollback"
        return $false
    }
}

# ========== 脚本入口 ==========
Write-Host "========================================" -ForegroundColor $ColorMagenta
Write-Host "    AI24X网站自动化部署脚本 v$ScriptVersion    " -ForegroundColor $ColorMagenta
Write-Host "========================================" -ForegroundColor $ColorMagenta
Write-Host ""

# 检查是否回滚模式
if ($Rollback) {
    Invoke-Rollback -Version $RollbackVersion
} else {
    # 执行部署
    $DeploymentResult = Start-Deployment
    
    if ($DeploymentResult) {
        Write-Host ""
        Write-Host "✅ 部署成功!" -ForegroundColor $ColorGreen
        Write-Host "   应用名称: $AppName" -ForegroundColor $ColorCyan
        Write-Host "   访问地址: http://localhost:3000" -ForegroundColor $ColorCyan
        Write-Host "   健康检查: http://localhost:3000/health" -ForegroundColor $ColorCyan
        Write-Host "   PM2状态: pm2 show $AppName" -ForegroundColor $ColorCyan
        Write-Host "   查看日志: pm2 logs $AppName" -ForegroundColor $ColorCyan
    } else {
        Write-Host ""
        Write-Host "❌ 部署失败!" -ForegroundColor $ColorRed
        Write-Host "   请检查日志文件: $LogFile" -ForegroundColor $ColorYellow
        Write-Host "   建议执行回滚: .\deploy.ps1 -Environment $Environment -Rollback" -ForegroundColor $ColorYellow
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor $ColorMagenta
Write-Host "部署脚本执行完成" -ForegroundColor $ColorMagenta
Write-Host "========================================" -ForegroundColor $ColorMagenta