#!/bin/bash

# AI24X海外节点部署脚本
# 新加坡生产服务器专用

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查Docker是否安装
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    log_info "Docker版本: $(docker --version)"
    log_info "Docker Compose版本: $(docker-compose --version)"
}

# 创建必要的目录
create_directories() {
    log_info "创建目录结构..."
    
    mkdir -p ./{nginx/conf.d,nginx/ssl,nginx/logs,postgresql/data,redis/data,backend/config,backend/logs,monitoring,prometheus_data,grafana_data,backup}
    
    log_info "目录结构创建完成"
}

# 生成环境变量文件
generate_env() {
    log_info "生成环境变量文件..."
    
    cat > .env << EOF
# AI24X海外节点环境变量
# 新加坡生产服务器

# PostgreSQL数据库
POSTGRES_DB=ai24x_production
POSTGRES_USER=ai24x_admin
POSTGRES_PASSWORD=$(openssl rand -base64 32)
POSTGRES_HOST=postgresql
POSTGRES_PORT=5432

# Redis缓存
REDIS_PASSWORD=$(openssl rand -base64 32)
REDIS_HOST=redis
REDIS_PORT=6379

# 后端应用
NODE_ENV=production
DATABASE_URL=postgresql://ai24x_admin:\${POSTGRES_PASSWORD}@postgresql:5432/ai24x_production
REDIS_URL=redis://:\${REDIS_PASSWORD}@redis:6379/0
SECRET_KEY=$(openssl rand -base64 64)
JWT_SECRET=$(openssl rand -base64 64)

# 监控系统
PROMETHEUS_DATA_DIR=./prometheus_data
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 16)

# 域名配置
DOMAIN=ai24x.com
EMAIL=admin@ai24x.com

# 时区
TZ=Asia/Singapore
EOF
    
    log_info "环境变量文件生成完成"
    log_warn "请检查 .env 文件中的敏感信息，并根据需要修改"
}

# 启动Docker服务
start_services() {
    log_info "启动Docker服务..."
    
    # 拉取最新镜像
    log_info "拉取Docker镜像..."
    docker-compose pull
    
    # 启动服务
    log_info "启动服务..."
    docker-compose up -d
    
    # 等待服务就绪
    log_info "等待服务启动..."
    sleep 30
    
    # 检查服务状态
    log_info "检查服务状态..."
    docker-compose ps
    
    # 显示服务日志
    log_info "显示服务日志（最后20行）..."
    docker-compose logs --tail=20
}

# 配置SSL证书（如果需要）
setup_ssl() {
    log_info "配置SSL证书..."
    
    read -p "是否配置SSL证书？ (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "请确保域名已解析到当前服务器IP"
        log_info "运行以下命令配置SSL："
        echo "docker-compose run --rm certbot certonly --webroot --webroot-path /var/www/certbot -d ai24x.com -d www.ai24x.com"
        echo "docker-compose exec nginx nginx -s reload"
    else
        log_warn "跳过SSL证书配置，请手动配置"
    fi
}

# 配置备份脚本
setup_backup() {
    log_info "配置备份脚本..."
    
    cat > backup/backup.sh << 'EOF'
#!/bin/bash

# 备份脚本
BACKUP_DIR="./backup"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${DATE}.tar.gz"

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

# 备份数据库
docker-compose exec -T postgresql pg_dump -U ai24x_admin ai24x_production > "${BACKUP_DIR}/database_${DATE}.sql"

# 备份配置文件
tar -czf "${BACKUP_FILE}" \
    .env \
    docker-compose.yml \
    nginx/conf.d \
    backend/config \
    monitoring \
    backup/*.sql

# 删除7天前的备份
find "${BACKUP_DIR}" -name "*.sql" -mtime +7 -delete
find "${BACKUP_DIR}" -name "*.tar.gz" -mtime +7 -delete

echo "备份完成: ${BACKUP_FILE}"
EOF
    
    chmod +x backup/backup.sh
    
    # 添加到cron（每天凌晨2点执行）
    (crontab -l 2>/dev/null; echo "0 2 * * * cd $(pwd) && ./backup/backup.sh >> ./backup/backup.log 2>&1") | crontab -
    
    log_info "备份脚本配置完成"
}

# 显示部署完成信息
show_completion() {
    echo ""
    echo "========================================"
    echo "AI24X海外节点部署完成！"
    echo "========================================"
    echo ""
    echo "服务状态："
    echo "  - PostgreSQL: localhost:5432 (仅本地访问)"
    echo "  - Redis: localhost:6379 (仅本地访问)"
    echo "  - 后端应用: localhost:8000 (仅本地访问)"
    echo "  - Nginx: http://localhost (公网访问)"
    echo "  - Prometheus: localhost:9090 (监控)"
    echo "  - Grafana: localhost:3000 (仪表盘)"
    echo ""
    echo "管理命令："
    echo "  docker-compose ps          # 查看服务状态"
    echo "  docker-compose logs        # 查看日志"
    echo "  docker-compose restart     # 重启服务"
    echo "  docker-compose down        # 停止服务"
    echo ""
    echo "备份命令："
    echo "  ./backup/backup.sh         # 手动备份"
    echo ""
    echo "监控地址："
    echo "  http://localhost:3000      # Grafana (admin/密码见.env)"
    echo "  http://localhost:9090      # Prometheus"
    echo ""
    echo "下一步："
    echo "  1. 配置域名DNS解析到服务器IP"
    echo "  2. 配置SSL证书（如果需要）"
    echo "  3. 访问 https://ai24x.com"
    echo "  4. 检查监控系统是否正常"
    echo ""
}

# 主函数
main() {
    log_info "开始AI24X海外节点部署"
    log_info "服务器: 新加坡生产节点"
    log_info "时间: $(date)"
    
    # 检查Docker
    check_docker
    
    # 创建目录
    create_directories
    
    # 生成环境变量
    generate_env
    
    # 启动服务
    start_services
    
    # 配置SSL
    setup_ssl
    
    # 配置备份
    setup_backup
    
    # 显示完成信息
    show_completion
    
    log_info "部署完成！"
}

# 执行主函数
main "$@"