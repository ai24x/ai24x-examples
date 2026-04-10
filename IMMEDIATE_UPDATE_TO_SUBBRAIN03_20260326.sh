#!/bin/bash
# AI24X网站立即更新脚本 - 副脑03专用
# 版本: 2026-03-26
# 执行: bash IMMEDIATE_UPDATE_TO_SUBBRAIN03_20260326.sh

set -e  # 遇到错误立即退出

echo "========================================="
echo "AI24X网站更新脚本 - 副脑03"
echo "开始时间: $(date)"
echo "========================================="

# 配置变量
PROJECT_DIR="/var/www/ai24x-website"
BACKUP_DIR="/var/www/backups"
GITEE_REPO="https://gitee.com/ai24x/ai24x-website.git"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# 1. 切换到项目目录
echo "[1/8] 切换到项目目录..."
cd "$PROJECT_DIR" || { echo "错误: 项目目录不存在: $PROJECT_DIR"; exit 1; }

# 2. 备份当前版本
echo "[2/8] 备份当前版本..."
mkdir -p "$BACKUP_DIR"
BACKUP_NAME="ai24x-website-backup-$TIMESTAMP"
cp -r "$PROJECT_DIR" "$BACKUP_DIR/$BACKUP_NAME"
echo "备份完成: $BACKUP_DIR/$BACKUP_NAME"

# 3. 停止当前服务
echo "[3/8] 停止当前服务..."
pm2 stop ai24x-website 2>/dev/null || echo "服务未运行或不存在，继续..."

# 4. 从Gitee拉取最新代码
echo "[4/8] 从Gitee拉取最新代码..."
if [ -d ".git" ]; then
    git fetch origin
    git reset --hard origin/master
    git clean -fd
else
    echo "警告: 不是git仓库，尝试重新克隆..."
    cd /var/www
    rm -rf ai24x-website-temp
    git clone "$GITEE_REPO" ai24x-website-temp
    rm -rf ai24x-website
    mv ai24x-website-temp ai24x-website
    cd ai24x-website
fi

# 5. 安装依赖
echo "[5/8] 安装Node.js依赖..."
npm install --production --no-audit --no-fund

# 6. 检查环境配置
echo "[6/8] 检查环境配置..."
if [ ! -f ".env" ]; then
    echo "警告: .env文件不存在，从模板创建..."
    if [ -f "deploy-config/.env.example" ]; then
        cp deploy-config/.env.example .env
        echo "请编辑 .env 文件并填写实际配置值！"
    fi
fi

# 7. 启动服务
echo "[7/8] 启动网站服务..."
pm2 start server.js --name ai24x-website || pm2 restart ai24x-website
pm2 save

# 8. 验证更新
echo "[8/8] 验证更新..."
sleep 5  # 等待服务启动

# 检查服务状态
if pm2 status ai24x-website | grep -q "online"; then
    echo "✅ 服务启动成功"
    
    # 测试网站访问
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/health | grep -q "200"; then
        echo "✅ 网站健康检查通过"
    else
        echo "⚠️  网站健康检查失败，但服务已运行"
    fi
else
    echo "❌ 服务启动失败，请检查日志: pm2 logs ai24x-website"
    exit 1
fi

echo "========================================="
echo "更新完成！"
echo "完成时间: $(date)"
echo "========================================="
echo ""
echo "后续操作:"
echo "1. 检查服务状态: pm2 status ai24x-website"
echo "2. 查看实时日志: pm2 logs ai24x-website"
echo "3. 测试网站访问: curl http://localhost:3000"
echo "4. 验证功能: 打开浏览器访问网站"
echo ""
echo "如有问题，请联系副脑01（首席开发官）"