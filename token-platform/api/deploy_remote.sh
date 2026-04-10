#!/bin/bash

# AI24X 副脑01 远程部署脚本
# 用于部署到副脑04提供的PostgreSQL数据库

set -e

echo "========================================"
echo "  AI24X 副脑01 远程部署脚本"
echo "  目标数据库: 43.160.246.30:5432"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查数据库连接
check_database_connection() {
    print_info "检查远程数据库连接..."
    
    # 使用psql检查连接
    if command -v psql &> /dev/null; then
        PGPASSWORD="ai24x_20240409" psql -h "43.160.246.30" -p 5432 -U "ai24x_admin" -d "ai24x" -c "\q" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            print_info "数据库连接测试成功"
            return 0
        else
            print_error "数据库连接测试失败"
            return 1
        fi
    else
        print_warning "未找到psql客户端，跳过命令行测试"
        
        # 使用Python测试连接
        python3 -c "
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
    print('Python数据库连接测试成功')
    exit(0)
except Exception as e:
    print(f'Python数据库连接测试失败: {e}')
    exit(1)
" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            print_info "Python数据库连接测试成功"
            return 0
        else
            print_error "数据库连接测试失败"
            return 1
        fi
    fi
}

# 更新环境配置
update_environment() {
    print_info "更新环境配置..."
    
    # 备份当前.env文件
    if [ -f ".env" ]; then
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        print_info "已备份当前.env文件"
    fi
    
    # 使用生产环境配置
    if [ -f ".env.production" ]; then
        cp .env.production .env
        print_info "已应用生产环境配置"
    else
        # 创建生产配置
        cat > .env << EOF
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
EOF
        print_info "已创建生产环境配置"
    fi
}

# 初始化数据库
initialize_database() {
    print_info "初始化远程数据库..."
    
    python3 -c "
import sys
sys.path.append('.')
try:
    from database import init_db
    print('正在初始化数据库表结构...')
    init_db()
    print('数据库初始化成功')
except Exception as e:
    print(f'数据库初始化失败: {e}')
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        print_info "数据库初始化完成"
    else
        print_error "数据库初始化失败"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    print_info "安装Python依赖..."
    
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt
        if [ $? -eq 0 ]; then
            print_info "依赖安装完成"
        else
            print_error "依赖安装失败"
            exit 1
        fi
    else
        print_error "未找到requirements.txt文件"
        exit 1
    fi
}

# 启动服务
start_service() {
    print_info "启动AI24X副脑01 API服务..."
    
    # 检查端口是否被占用
    if lsof -ti:8000 &> /dev/null; then
        print_warning "端口8000已被占用，尝试停止现有服务..."
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # 启动服务（后台运行）
    nohup python3 run.py > app.log 2>&1 &
    SERVER_PID=$!
    
    sleep 5
    
    # 检查服务是否启动成功
    if kill -0 $SERVER_PID 2>/dev/null; then
        print_info "服务启动成功，PID: $SERVER_PID"
        print_info "日志文件: app.log"
        
        # 保存PID到文件
        echo $SERVER_PID > server.pid
        
        # 测试健康检查
        sleep 2
        if curl -s http://localhost:8000/health > /dev/null; then
            print_info "健康检查: 通过"
        else
            print_warning "健康检查: 失败（服务可能仍在启动中）"
        fi
    else
        print_error "服务启动失败，请查看app.log文件"
        exit 1
    fi
}

# 运行测试
run_tests() {
    print_info "运行API测试..."
    
    if [ -f "test_api.py" ]; then
        # 等待服务完全启动
        sleep 5
        
        python3 test_api.py
        
        if [ $? -eq 0 ]; then
            print_info "API测试通过"
        else
            print_warning "API测试失败，但服务仍会继续运行"
        fi
    else
        print_warning "未找到测试文件，跳过测试"
    fi
}

# 显示部署信息
show_deployment_info() {
    echo ""
    echo "========================================"
    echo "  远程部署完成！"
    echo "========================================"
    echo ""
    echo "部署信息:"
    echo "  - 数据库: 43.160.246.30:5432/ai24x"
    echo "  - API服务: http://localhost:8000"
    echo "  - 服务状态: 运行中"
    echo "  - PID文件: server.pid"
    echo "  - 日志文件: app.log"
    echo ""
    echo "访问地址:"
    echo "  - API文档: http://localhost:8000/docs"
    echo "  - 健康检查: http://localhost:8000/health"
    echo ""
    echo "数据库信息:"
    echo "  - 主机: 43.160.246.30"
    echo "  - 端口: 5432"
    echo "  - 数据库: ai24x"
    echo "  - 用户: ai24x_admin"
    echo ""
    echo "管理命令:"
    echo "  - 停止服务: kill \$(cat server.pid)"
    echo "  - 查看日志: tail -f app.log"
    echo "  - 重启服务: ./deploy_remote.sh restart"
    echo ""
    echo "测试命令:"
    echo '  curl -X POST "http://localhost:8000/v1/chat/run?user_id=test_user_001" \'
    echo '    -H "Content-Type: application/json" \'
    echo '    -d '\''{"prompt":"测试远程数据库连接","model":"gpt-3.5-turbo"}'\'''
    echo ""
}

# 停止服务
stop_service() {
    print_info "停止服务..."
    
    if [ -f "server.pid" ]; then
        PID=$(cat server.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            sleep 2
            print_info "服务已停止"
            rm -f server.pid
        else
            print_warning "服务未在运行"
            rm -f server.pid
        fi
    else
        print_warning "未找到PID文件"
    fi
}

# 重启服务
restart_service() {
    print_info "重启服务..."
    stop_service
    sleep 2
    start_service
    run_tests
    show_deployment_info
}

# 显示帮助
show_help() {
    echo "使用: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  deploy      部署到远程数据库（默认）"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  status      查看服务状态"
    echo "  test        测试数据库连接"
    echo "  help        显示帮助"
    echo ""
}

# 查看状态
check_status() {
    print_info "检查服务状态..."
    
    # 检查数据库连接
    check_database_connection
    
    # 检查服务进程
    if [ -f "server.pid" ]; then
        PID=$(cat server.pid)
        if kill -0 $PID 2>/dev/null; then
            print_info "API服务正在运行，PID: $PID"
            
            # 检查端口
            if lsof -ti:8000 &> /dev/null; then
                print_info "端口8000监听正常"
                
                # 测试健康检查
                if curl -s http://localhost:8000/health > /dev/null; then
                    print_info "健康检查: 通过"
                else
                    print_warning "健康检查: 失败"
                fi
            else
                print_warning "端口8000未监听"
            fi
        else
            print_warning "服务PID存在但进程未运行"
            rm -f server.pid
        fi
    else
        print_warning "API服务未运行"
    fi
}

# 主函数
main() {
    COMMAND=${1:-"deploy"}
    
    case $COMMAND in
        "deploy")
            check_database_connection
            update_environment
            install_dependencies
            initialize_database
            start_service
            run_tests
            show_deployment_info
            ;;
        "start")
            start_service
            ;;
        "stop")
            stop_service
            ;;
        "restart")
            restart_service
            ;;
        "status")
            check_status
            ;;
        "test")
            check_database_connection
            ;;
        "help")
            show_help
            ;;
        *)
            print_error "未知命令: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"