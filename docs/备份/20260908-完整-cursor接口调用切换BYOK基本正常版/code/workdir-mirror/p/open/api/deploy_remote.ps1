# AI24X 副脑01 远程部署脚本 (Windows)
# 用于部署到副脑04提供的PostgreSQL数据库

Write-Host "========================================" -ForegroundColor Green
Write-Host "  AI24X 副脑01 远程部署脚本 (Windows)" -ForegroundColor Green
Write-Host "  目标数据库: 43.160.246.30:5432" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

# 检查数据库连接
function Check-DatabaseConnection {
    Write-Info "检查远程数据库连接..."
    
    try {
        # 使用Python测试连接
        python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='43.160.246.30',
        port=5432,
        database='ai24x',
        user='ai24x_admin',
        password='ai24x_20240409'
    )
    conn.close()
    print('SUCCESS: Database connection test passed')
    exit(0)
except Exception as e:
    print(f'ERROR: Database connection test failed: {e}')
    exit(1)
"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "数据库连接测试成功"
            return $true
        } else {
            Write-Error "数据库连接测试失败"
            return $false
        }
    } catch {
        Write-Error "数据库连接测试异常: $_"
        return $false
    }
}

# 更新环境配置
function Update-Environment {
    Write-Info "更新环境配置..."
    
    # 备份当前.env文件
    if (Test-Path ".env") {
        $backupName = ".env.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item ".env" $backupName
        Write-Info "已备份当前.env文件: $backupName"
    }
    
    # 使用生产环境配置
    if (Test-Path ".env.production") {
        Copy-Item ".env.production" ".env"
        Write-Info "已应用生产环境配置"
    } else {
        # 创建生产配置
        @"
# Production Environment
DATABASE_URL=postgresql://ai24x_admin:ai24x_20240409@43.160.246.30:5432/ai24x
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
SECRET_KEY=ai24x-subbrain01-production-secret-key-2026
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENABLE_RATE_LIMITING=true
ENABLE_CACHING=true
LOG_LEVEL=INFO
LOG_FORMAT=json
"@ | Out-File -FilePath ".env" -Encoding UTF8
        
        Write-Info "已创建生产环境配置"
    }
}

# 初始化数据库
function Initialize-Database {
    Write-Info "初始化远程数据库..."
    
    python -c "
import sys
sys.path.append('.')
try:
    from database import init_db
    print('Initializing database tables...')
    init_db()
    print('SUCCESS: Database initialized successfully')
except Exception as e:
    print(f'ERROR: Database initialization failed: {e}')
    sys.exit(1)
"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "数据库初始化完成"
    } else {
        Write-Error "数据库初始化失败"
        exit 1
    }
}

# 安装依赖
function Install-Dependencies {
    Write-Info "安装Python依赖..."
    
    if (Test-Path "requirements.txt") {
        pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Success "依赖安装完成"
        } else {
            Write-Error "依赖安装失败"
            exit 1
        }
    } else {
        Write-Error "未找到requirements.txt文件"
        exit 1
    }
}

# 启动服务
function Start-Service {
    Write-Info "启动AI24X副脑01 API服务..."
    
    # 检查端口是否被占用
    $portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($portInUse) {
        Write-Warning "端口8000已被占用，尝试停止现有进程..."
        
        $portInUse | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        
        Start-Sleep -Seconds 2
    }
    
    # 启动服务
    $process = Start-Process python -ArgumentList "run.py" -PassThru -NoNewWindow
    
    Start-Sleep -Seconds 5
    
    # 检查服务是否启动成功
    if (-not $process.HasExited) {
        $pid = $process.Id
        Write-Success "服务启动成功，PID: $pid"
        Write-Info "日志文件: app.log"
        
        # 保存PID到文件
        $pid | Out-File -FilePath "server.pid" -Encoding ASCII
        
        # 测试健康检查
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                Write-Success "健康检查: 通过"
            }
        } catch {
            Write-Warning "健康检查: 失败（服务可能仍在启动中）"
        }
    } else {
        Write-Error "服务启动失败"
        exit 1
    }
}

# 运行测试
function Run-Tests {
    Write-Info "运行API测试..."
    
    if (Test-Path "test_api.py") {
        # 等待服务完全启动
        Start-Sleep -Seconds 5
        
        python test_api.py
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "API测试通过"
        } else {
            Write-Warning "API测试失败，但服务仍会继续运行"
        }
    } else {
        Write-Warning "未找到测试文件，跳过测试"
    }
}

# 显示部署信息
function Show-DeploymentInfo {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  远程部署完成！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "部署信息:" -ForegroundColor Cyan
    Write-Host "  - 数据库: 43.160.246.30:5432/ai24x"
    Write-Host "  - API服务: http://localhost:8000"
    Write-Host "  - 服务状态: 运行中"
    Write-Host "  - PID文件: server.pid"
    Write-Host "  - 日志文件: app.log"
    Write-Host ""
    Write-Host "访问地址:" -ForegroundColor Cyan
    Write-Host "  - API文档: http://localhost:8000/docs"
    Write-Host "  - 健康检查: http://localhost:8000/health"
    Write-Host ""
    Write-Host "数据库信息:" -ForegroundColor Cyan
    Write-Host "  - 主机: 43.160.246.30"
    Write-Host "  - 端口: 5432"
    Write-Host "  - 数据库: ai24x"
    Write-Host "  - 用户: ai24x_admin"
    Write-Host ""
    Write-Host "管理命令:" -ForegroundColor Cyan
    Write-Host "  - 停止服务: Stop-Service (在此脚本中)"
    Write-Host "  - 重启服务: Restart-Service (在此脚本中)"
    Write-Host ""
    Write-Host "测试命令:" -ForegroundColor Cyan
    Write-Host '  curl -X POST "http://localhost:8000/v1/chat/run?user_id=test_user_001" \'
    Write-Host '    -H "Content-Type: application/json" \'
    Write-Host '    -d "{\"prompt\":\"测试远程数据库连接\",\"model\":\"gpt-3.5-turbo\"}"'
    Write-Host ""
}

# 停止服务
function Stop-Service {
    Write-Info "停止服务..."
    
    if (Test-Path "server.pid") {
        $pid = Get-Content "server.pid" -Raw
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Success "服务已停止"
            Remove-Item "server.pid" -Force
        } catch {
            Write-Warning "停止服务失败: $_"
        }
    } else {
        Write-Warning "未找到PID文件"
    }
}

# 重启服务
function Restart-Service {
    Write-Info "重启服务..."
    Stop-Service
    Start-Sleep -Seconds 2
    Start-Service
    Run-Tests
    Show-DeploymentInfo
}

# 查看状态
function Check-Status {
    Write-Info "检查服务状态..."
    
    # 检查数据库连接
    Check-DatabaseConnection
    
    # 检查服务进程
    if (Test-Path "server.pid") {
        $pid = Get-Content "server.pid" -Raw
        try {
            $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($process) {
                Write-Success "API服务正在运行，PID: $pid"
                
                # 检查端口
                $portCheck = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
                if ($portCheck) {
                    Write-Info "端口8000监听正常"
                    
                    # 测试健康检查
                    try {
                        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3
                        if ($response.StatusCode -eq 200) {
                            Write-Success "健康检查: 通过"
                        }
                    } catch {
                        Write-Warning "健康检查: 失败"
                    }
                } else {
                    Write-Warning "端口8000未监听"
                }
            } else {
                Write-Warning "服务PID存在但进程未运行"
                Remove-Item "server.pid" -Force
            }
        } catch {
            Write-Warning "检查进程失败: $_"
        }
    } else {
        Write-Warning "API服务未运行"
    }
}

# 主函数
function Main {
    param(
        [string]$Command = "deploy"
    )
    
    switch ($Command.ToLower()) {
        "deploy" {
            if (-not (Check-DatabaseConnection)) {
                Write-Error "数据库连接测试失败，部署中止"
                exit 1
            }
            Update-Environment
            Install-Dependencies
            Initialize-Database
            Start-Service
            Run-Tests
            Show-DeploymentInfo
        }
        "start" {
            Start-Service
        }
        "stop" {
            Stop-Service
        }
        "restart" {
            Restart-Service
        }
        "status" {
            Check-Status
        }
        "test" {
            Check-DatabaseConnection
        }
        "help" {
            Write-Host "使用: .\deploy_remote.ps1 [命令]" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "命令:" -ForegroundColor Cyan
            Write-Host "  deploy      部署到远程数据库（默认）"
            Write-Host "  start       启动服务"
            Write-Host "  stop        停止服务"
            Write-Host "  restart     重启服务"
            Write-Host "  status      查看服务状态"
            Write-Host "  test        测试数据库连接"
            Write-Host "  help        显示帮助"
            Write-Host ""
        }
        default {
            Write-Error "未知命令: $Command"
            Write-Host "使用: .\deploy_remote.ps1 help 查看可用命令"
            exit 1
        }
    }
}

# 执行主函数
if ($args.Count -eq 0) {
    Main
} else {
    Main -Command $args[0]
}