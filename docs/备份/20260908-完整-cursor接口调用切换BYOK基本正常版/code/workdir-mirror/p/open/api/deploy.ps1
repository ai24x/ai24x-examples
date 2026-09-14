# AI24X 副脑01 API Windows 部署脚本

Write-Host "========================================" -ForegroundColor Green
Write-Host "  AI24X 副脑01 API Windows 部署" -ForegroundColor Green
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

# 检查Python
function Check-Python {
    Write-Info "检查Python版本..."
    
    $pythonPath = $null
    $pythonVersion = $null
    
    # 尝试查找python3或python
    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        $pythonPath = "python3"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonPath = "python"
    } else {
        Write-Error "未找到Python，请先安装Python 3.8+"
        exit 1
    }
    
    # 获取Python版本
    try {
        $versionOutput = & $pythonPath --version 2>&1
        if ($versionOutput -match "Python (\d+\.\d+\.\d+)") {
            $pythonVersion = $matches[1]
            Write-Info "检测到Python版本: $pythonVersion"
            
            # 检查版本是否 >= 3.8
            $versionParts = $pythonVersion -split '\.'
            $major = [int]$versionParts[0]
            $minor = [int]$versionParts[1]
            
            if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 8)) {
                Write-Error "需要Python 3.8+，当前版本: $pythonVersion"
                exit 1
            }
        }
    } catch {
        Write-Error "无法获取Python版本: $_"
        exit 1
    }
    
    return $pythonPath
}

# 设置虚拟环境
function Setup-Venv {
    param([string]$PythonPath)
    
    Write-Info "设置Python虚拟环境..."
    
    if (-not (Test-Path "venv")) {
        & $PythonPath -m venv venv
        if ($LASTEXITCODE -eq 0) {
            Write-Info "虚拟环境创建成功"
        } else {
            Write-Error "虚拟环境创建失败"
            exit 1
        }
    } else {
        Write-Info "虚拟环境已存在"
    }
    
    # 激活虚拟环境
    $activateScript = "venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        . $activateScript
        Write-Info "虚拟环境已激活"
    } else {
        Write-Error "无法找到虚拟环境激活脚本"
        exit 1
    }
}

# 安装依赖
function Install-Dependencies {
    Write-Info "安装Python依赖..."
    
    if (Test-Path "requirements.txt") {
        pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Info "依赖安装完成"
        } else {
            Write-Error "依赖安装失败"
            exit 1
        }
    } else {
        Write-Error "未找到requirements.txt文件"
        exit 1
    }
}

# 配置环境变量
function Setup-Env {
    Write-Info "配置环境变量..."
    
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Warning "已创建.env文件，请编辑该文件配置数据库连接等信息"
            Write-Warning "编辑命令: notepad .env"
        } else {
            Write-Error "未找到.env.example文件"
            exit 1
        }
    } else {
        Write-Info ".env文件已存在"
    }
}

# 初始化数据库
function Init-Database {
    Write-Info "初始化数据库..."
    
    if (Test-Path ".env") {
        # 尝试初始化数据库
        try {
            python -c "
try:
    from database import init_db
    init_db()
    print('数据库初始化成功')
except Exception as e:
    print(f'数据库初始化失败: {e}')
    print('请确保:')
    print('1. PostgreSQL服务正在运行')
    print('2. .env中的DATABASE_URL配置正确')
    print('3. 数据库用户有创建表的权限')
"
        } catch {
            Write-Warning "数据库初始化失败: $_"
            Write-Warning "请手动检查数据库配置"
        }
    } else {
        Write-Warning "未找到.env文件，跳过数据库初始化"
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
    
    Start-Sleep -Seconds 3
    
    # 检查服务是否启动成功
    if (-not $process.HasExited) {
        $pid = $process.Id
        Write-Info "服务启动成功，PID: $pid"
        Write-Info "API文档: http://localhost:8000/docs"
        Write-Info "健康检查: http://localhost:8000/health"
        
        # 保存PID到文件
        $pid | Out-File -FilePath "server.pid" -Encoding ASCII
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
            Write-Info "测试通过"
        } else {
            Write-Warning "测试失败，但服务仍会继续运行"
        }
    } else {
        Write-Warning "未找到测试文件，跳过测试"
    }
}

# 显示部署信息
function Show-DeploymentInfo {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  部署完成！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "服务信息:" -ForegroundColor Cyan
    Write-Host "  - 服务状态: 运行中" -ForegroundColor Green
    Write-Host "  - PID文件: server.pid"
    Write-Host ""
    Write-Host "访问地址:" -ForegroundColor Cyan
    Write-Host "  - API文档: http://localhost:8000/docs"
    Write-Host "  - ReDoc文档: http://localhost:8000/redoc"
    Write-Host "  - 健康检查: http://localhost:8000/health"
    Write-Host ""
    Write-Host "主要接口:" -ForegroundColor Cyan
    Write-Host "  - POST /v1/chat/run - 处理聊天请求"
    Write-Host "  - GET  /v1/user/info - 获取用户信息"
    Write-Host ""
    Write-Host "管理命令:" -ForegroundColor Cyan
    Write-Host "  - 停止服务: Stop-Service (在此脚本中)"
    Write-Host "  - 重启服务: Restart-Service (在此脚本中)"
    Write-Host ""
    Write-Host "测试用户:" -ForegroundColor Cyan
    Write-Host "  - 用户ID: test_user_001"
    Write-Host "  - 类型: 免费用户 (100次/日)"
    Write-Host ""
    Write-Host "快速测试:" -ForegroundColor Cyan
    Write-Host '  curl -X POST "http://localhost:8000/v1/chat/run?user_id=test_user_001" \'
    Write-Host '    -H "Content-Type: application/json" \'
    Write-Host '    -d "{\"prompt\":\"你好\",\"model\":\"gpt-3.5-turbo\"}"'
    Write-Host ""
}

# 停止服务
function Stop-Service {
    Write-Info "停止服务..."
    
    if (Test-Path "server.pid") {
        $pid = Get-Content "server.pid" -Raw
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Info "服务已停止"
            Remove-Item "server.pid" -Force
        } catch {
            Write-Warning "停止服务失败: $_"
        }
    } else {
        Write-Warning "未找到PID文件，尝试停止端口8000的进程..."
        
        $processes = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | 
            Select-Object -ExpandProperty OwningProcess -Unique
        
        foreach ($procId in $processes) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
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
    
    if (Test-Path "server.pid") {
        $pid = Get-Content "server.pid" -Raw
        try {
            $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($process) {
                Write-Info "服务正在运行，PID: $pid"
                
                # 检查端口
                $portCheck = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
                if ($portCheck) {
                    Write-Info "端口8000监听正常"
                    
                    # 测试健康检查
                    try {
                        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3
                        if ($response.StatusCode -eq 200) {
                            Write-Info "健康检查: 通过" -ForegroundColor Green
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
        Write-Warning "服务未运行"
    }
    
    # 检查虚拟环境
    if (Test-Path "venv") {
        Write-Info "虚拟环境: 已存在"
    } else {
        Write-Warning "虚拟环境: 未创建"
    }
    
    # 检查.env文件
    if (Test-Path ".env") {
        Write-Info "配置文件: 已存在"
    } else {
        Write-Warning "配置文件: 未创建"
    }
}

# 主函数
function Main {
    param(
        [string]$Command = "deploy"
    )
    
    switch ($Command.ToLower()) {
        "deploy" {
            $pythonPath = Check-Python
            Setup-Venv -PythonPath $pythonPath
            Install-Dependencies
            Setup-Env
            Init-Database
            Start-Service
            Run-Tests
            Show-DeploymentInfo
        }
        "start" {
            $pythonPath = Check-Python
            Setup-Venv -PythonPath $pythonPath
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
            $pythonPath = Check-Python
            Setup-Venv -PythonPath $pythonPath
            Run-Tests
        }
        "help" {
            Write-Host "使用: .\deploy.ps1 [命令]" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "命令:" -ForegroundColor Cyan
            Write-Host "  deploy      部署服务（默认）"
            Write-Host "  start       启动服务"
            Write-Host "  stop        停止服务"
            Write-Host "  restart     重启服务"
            Write-Host "  status      查看服务状态"
            Write-Host "  test        运行测试"
            Write-Host "  help        显示帮助"
            Write-Host ""
        }
        default {
            Write-Error "未知命令: $Command"
            Write-Host "使用: .\deploy.ps1 help 查看可用命令"
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