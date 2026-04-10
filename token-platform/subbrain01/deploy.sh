#!/bin/bash

# AI24X 副脑01 API 部署脚本

set -e

echo "========================================"
echo "  AI24X 副脑01 API 部署开始"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数：打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Python版本
check_python() {
    print_info "检查Python版本..."
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "未找到Python，请先安装Python 3.8+"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_info "检测到Python版本: $PYTHON_VERSION"
    
    # 检查版本是否 >= 3.8
    MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
    
    if [ $MAJOR -lt 3 ] || [ $MAJOR -eq 3 -a $MINOR -lt 8 ]; then
        print_error "需要Python 3.8+，当前版本: $PYTHON_VERSION"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    print_info "检查系统依赖..."
    
    # 检查pip
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        print_warning "未找到pip，尝试安装..."
        $PYTHON_CMD -m ensurepip --upgrade
    fi
    
    # 检查PostgreSQL客户端（可选）
    if command -v psql &> /dev/null; then
        print_info "检测到PostgreSQL客户端"
    else
        print_warning "未找到PostgreSQL客户端，数据库操作可能受限"
    fi
}

# 设置虚拟环境
setup_venv() {
    print_info "设置Python虚拟环境..."
    
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
        print_info "虚拟环境创建成功"
    else
        print_info "虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    else
        print_error "无法找到虚拟环境激活脚本"
        exit 1
    fi
    
    # 升级pip
    print_info "升级pip..."
    pip install --upgrade pip
}

# 安装依赖
install_dependencies() {
    print_info "安装Python依赖..."
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_info "依赖安装完成"
    else
        print_error "未找到requirements.txt文件"
        exit 1
    fi
}

# 配置环境变量
setup_env() {
    print_info "配置环境变量..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_warning "已创建.env文件，请编辑该文件配置数据库连接等信息"
            print_warning "编辑命令: nano .env 或 vim .env"
        else
            print_error "未找到.env.example文件"
            exit 1
        fi
    else
        print_info ".env文件已存在"
    fi
}

# 初始化数据库
init_database() {
    print_info "初始化数据库..."
    
    # 检查数据库连接
    if [ -f ".env" ]; then
        # 从.env文件提取数据库URL（简化版）
        if grep -q "DATABASE_URL" .env; then
            DB_URL=$(grep "DATABASE_URL" .env | cut -d '=' -f2-)
            print_info "数据库URL: $DB_URL"
            
            # 尝试初始化数据库
            $PYTHON_CMD -c "
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
        else
            print_warning "未找到DATABASE_URL配置，跳过数据库初始化"
        fi
    else
        print_warning "未找到.env文件，跳过数据库初始化"
    fi
}

# 启动服务
start_service() {
    print_info "启动AI24X副脑01 API服务..."
    
    # 检查服务是否已在运行
    if lsof -ti:8000 &> /dev/null; then
        print_warning "端口8000已被占用，尝试停止现有服务..."
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # 启动服务（后台运行）
    nohup $PYTHON_CMD run.py > app.log 2>&1 &
    SERVER_PID=$!
    
    sleep 3
    
    # 检查服务是否启动成功
    if kill -0 $SERVER_PID 2>/dev/null; then
        print_info "服务启动成功，PID: $SERVER_PID"
        print_info "日志文件: app.log"
        print_info "API文档: http://localhost:8000/docs"
        print_info "健康检查: http://localhost:8000/health"
        
        # 保存PID到文件
        echo $SERVER_PID > server.pid
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
        
        $PYTHON_CMD test_api.py
        
        if [ $? -eq 0 ]; then
            print_info "测试通过"
        else
            print_warning "测试失败，但服务仍会继续运行"
        fi
    else
        print_warning "未找到测试文件，跳过测试"
    fi
}

# 显示部署信息
show_deployment_info() {
    echo ""
    echo "========================================"
    echo "  部署完成！"
    echo "========================================"
    echo ""
    echo "服务信息:"
    echo "  - 服务状态: ${GREEN}运行中${NC}"
    echo "  - PID文件: server.pid"
    echo "  - 日志文件: app.log"
    echo ""
    echo "访问地址:"
    echo "  - API文档: http://localhost:8000/docs"
    echo "  - ReDoc文档: http://localhost:8000/redoc"
    echo "  - 健康检查: http://localhost:8000/health"
    echo ""
    echo "主要接口:"
    echo "  - POST /v1/chat/run - 处理聊天请求"
    echo "  - GET  /v1/user/info - 获取用户信息"
    echo ""
    echo "管理命令:"
    echo "  - 停止服务: kill \$(cat server.pid)"
    echo "  - 查看日志: tail -f app.log"
    echo "  - 重启服务: ./deploy.sh restart"
    echo ""
    echo "测试用户:"
    echo "  - 用户ID: test_user_001"
    echo "  - 类型: 免费用户 (100次/日)"
    echo ""
    echo "快速测试:"
    echo "  curl -X POST \"http://localhost:8000/v1/chat/run?user_id=test_user_001\" \\"
    echo "    -H \"Content-Type: application/json\" \\"
    echo "    -d '{\"prompt\":\"你好\",\"model\":\"gpt-3.5-turbo\"}'"
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
        print_warning "未找到PID文件，尝试停止端口8000的进程..."
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
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

# 清理
cleanup() {
    print_info "清理..."
    
    # 停止服务
    stop_service
    
    # 删除虚拟环境
    if [ -d "venv" ]; then
        rm -rf venv
        print_info "虚拟环境已删除"
    fi
    
    # 删除日志文件
    rm -f app.log server.pid
    
    print_info "清理完成"
}

# 显示帮助
show_help() {
    echo "使用: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  deploy      部署服务（默认）"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  status      查看服务状态"
    echo "  test        运行测试"
    echo "  clean       清理环境"
    echo "  help        显示帮助"
    echo ""
}

# 查看状态
check_status() {
    print_info "检查服务状态..."
    
    if [ -f "server.pid" ]; then
        PID=$(cat server.pid)
        if kill -0 $PID 2>/dev/null; then
            print_info "服务正在运行，PID: $PID"
            
            # 检查端口
            if lsof -ti:8000 &> /dev/null; then
                print_info "端口8000监听正常"
                
                # 测试健康检查
                if command -v curl &> /dev/null; then
                    if curl -s http://localhost:8000/health > /dev/null; then
                        print_info "健康检查: ${GREEN}通过${NC}"
                    else
                        print_warning "健康检查: ${YELLOW}失败${NC}"
                    fi
                fi
            else
                print_warning "端口8000未监听"
            fi
        else
            print_warning "服务PID存在但进程未运行"
            rm -f server.pid
        fi
    else
        print_warning "服务未运行"
    fi
    
    # 检查虚拟环境
    if [ -d "venv" ]; then
        print_info "虚拟环境: 已存在"
    else
        print_warning "虚拟环境: 未创建"
    fi
    
    # 检查.env文件
    if [ -f ".env" ]; then
        print_info "配置文件: 已存在"
    else
        print_warning "配置文件: 未创建"
    fi
}

# 主函数
main() {
    COMMAND=${1:-"deploy"}
    
    case $COMMAND in
        "deploy")
            check_python
            check_dependencies
            setup_venv
            install_dependencies
            setup_env
            init_database
            start_service
            run_tests
            show_deployment_info
            ;;
        "start")
            setup_venv
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
            setup_venv
            run_tests
            ;;
        "clean")
            cleanup
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