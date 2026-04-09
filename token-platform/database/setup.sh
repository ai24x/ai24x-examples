#!/bin/bash
# AI24X Token平台 - PostgreSQL数据库初始化脚本
# 生成时间: 2026-04-10 02:09 GMT+8
# 副脑04 - 国际节点运维官 (新加坡节点)

# ====================
# 配置信息 (与connection.txt保持一致)
# ====================
POSTGRES_HOST="43.160.246.30"
POSTGRES_PORT="5432"
POSTGRES_DB="ai24x"
POSTGRES_USER="ai24x_admin"
POSTGRES_PASSWORD="ai24x_20240409"

# ====================
# 颜色输出定义
# ====================
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ====================
# 函数定义
# ====================
log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_info() {
    echo -e "[*] $1"
}

# ====================
# 检查依赖
# ====================
check_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查psql是否可用
    if ! command -v psql &> /dev/null; then
        log_error "psql命令未找到，请安装PostgreSQL客户端"
        log_info "Ubuntu/Debian: sudo apt-get install postgresql-client"
        log_info "CentOS/RHEL: sudo yum install postgresql"
        log_info "macOS: brew install postgresql"
        exit 1
    fi
    log_success "PostgreSQL客户端可用"
    
    # 检查网络连接
    if ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT" &> /dev/null; then
        log_warning "无法连接到数据库主机 $POSTGRES_HOST:$POSTGRES_PORT"
        log_warning "请检查网络连接和防火墙设置"
    else
        log_success "数据库主机可访问"
    fi
}

# ====================
# 创建数据库和用户
# ====================
setup_database() {
    log_info "设置数据库和用户..."
    
    # 使用postgres超级用户连接（需要本地信任认证或密码）
    # 如果无法连接，请修改pg_hba.conf或使用其他认证方式
    
    # 1. 创建数据库（如果不存在）
    log_info "创建数据库 '$POSTGRES_DB'..."
    PGPASSWORD="postgres" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U postgres -c "CREATE DATABASE $POSTGRES_DB;" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "数据库创建成功"
    else
        log_warning "数据库可能已存在，继续执行..."
    fi
    
    # 2. 创建用户（如果不存在）
    log_info "创建用户 '$POSTGRES_USER'..."
    PGPASSWORD="postgres" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U postgres -c "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "用户创建成功"
    else
        log_warning "用户可能已存在，继续执行..."
    fi
    
    # 3. 授予权限
    log_info "授予用户权限..."
    PGPASSWORD="postgres" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "权限授予成功"
    else
        log_error "权限授予失败"
        exit 1
    fi
    
    # 4. 授予超级用户权限（可选，用于开发环境）
    log_info "授予超级用户权限（开发环境）..."
    PGPASSWORD="postgres" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U postgres -d "$POSTGRES_DB" -c "ALTER USER $POSTGRES_USER WITH SUPERUSER;" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_success "超级用户权限授予成功"
    else
        log_warning "超级用户权限授予失败，继续执行..."
    fi
}

# ====================
# 执行SQL脚本
# ====================
execute_schema() {
    log_info "执行数据库表结构脚本..."
    
    # 检查schema.sql文件是否存在
    if [ ! -f "schema.sql" ]; then
        log_error "schema.sql文件不存在"
        exit 1
    fi
    
    # 执行SQL脚本
    log_info "正在创建表结构..."
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f schema.sql
    
    if [ $? -eq 0 ]; then
        log_success "表结构创建成功"
    else
        log_error "表结构创建失败"
        exit 1
    fi
}

# ====================
# 验证安装
# ====================
verify_installation() {
    log_info "验证数据库安装..."
    
    # 查询表数量
    table_count=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d '[:space:]')
    
    if [ -n "$table_count" ] && [ "$table_count" -ge 10 ]; then
        log_success "验证成功: 找到 $table_count 张表"
        log_success "数据库初始化完成！"
    else
        log_warning "表数量少于预期 (当前: $table_count, 预期: 10+)"
        log_warning "请检查schema.sql执行结果"
    fi
    
    # 显示连接信息
    echo ""
    log_info "数据库连接信息:"
    echo "  主机: $POSTGRES_HOST"
    echo "  端口: $POSTGRES_PORT"
    echo "  数据库: $POSTGRES_DB"
    echo "  用户: $POSTGRES_USER"
    echo "  密码: $POSTGRES_PASSWORD"
    echo ""
    log_info "测试连接命令:"
    echo "  psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB"
}

# ====================
# 主程序
# ====================
main() {
    echo "========================================="
    echo "  AI24X Token平台 - 数据库初始化脚本"
    echo "========================================="
    
    # 检查依赖
    check_dependencies
    
    # 设置数据库
    setup_database
    
    # 执行表结构
    execute_schema
    
    # 验证安装
    verify_installation
    
    echo "========================================="
    echo "  初始化完成！"
    echo "========================================="
}

# 执行主程序
main "$@"