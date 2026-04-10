# Gitee推送与副脑03更新报告
## 执行时间：2026-03-26 16:15 GMT+8

## 📊 执行摘要
✅ **Gitee推送完成**：AI24X网站完整项目已成功上传到Gitee仓库
✅ **代码版本**：初始提交 (ee1a01b) - 211个文件，58,834行代码
✅ **仓库地址**：https://gitee.com/ai24x/ai24x-website.git
✅ **推送状态**：强制推送成功，master分支已更新

## 🚀 副脑03更新指令

### 1. 立即执行更新命令（SSH到副脑03服务器）
```bash
# SSH连接到副脑03服务器
ssh root@123.207.199.238

# 切换到网站目录
cd /var/www/ai24x-website

# 备份当前版本
cp -r . ../ai24x-website-backup-$(date +%Y%m%d-%H%M%S)

# 从Gitee拉取最新代码
git fetch origin
git reset --hard origin/master

# 安装依赖
npm install --production

# 重启服务
pm2 restart ai24x-website || pm2 start server.js --name ai24x-website
```

### 2. 自动化更新脚本（推荐）
```bash
# 下载并执行自动化更新脚本
curl -sSL https://gitee.com/ai24x/ai24x-website/raw/master/deploy-config/deploy.ps1 -o update.ps1
pwsh -File update.ps1 -Environment production -Force
```

## 🔧 需要更新的配置

### 核心配置文件更新
1. **环境变量配置** (`deploy-config/.env.example` → `.env`)
   - 复制模板文件并填写实际值
   - 特别注意：JWT_SECRET、数据库路径、支付配置

2. **服务器配置** (`server.js` 或 `server-*.js`)
   - 检查端口配置（默认3000）
   - 验证数据库连接路径
   - 确认SSL/TLS配置（如启用HTTPS）

3. **数据库迁移**
   - 备份现有数据库：`cp -r data data-backup-$(date +%Y%m%d)`
   - 检查数据文件兼容性：`data/` 目录下所有JSON文件

### 服务管理配置
1. **PM2配置** (`ecosystem.config.js`)
   ```javascript
   module.exports = {
     apps: [{
       name: 'ai24x-website',
       script: 'server.js',
       instances: 'max',
       exec_mode: 'cluster',
       env: {
         NODE_ENV: 'production',
         PORT: 3000
       }
     }]
   }
   ```

2. **Nginx反向代理**（如使用）
   ```nginx
   server {
     listen 80;
     server_name ai24x.com www.ai24x.com;
     
     location / {
       proxy_pass http://localhost:3000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection 'upgrade';
       proxy_set_header Host $host;
       proxy_cache_bypass $http_upgrade;
     }
   }
   ```

3. **防火墙规则**
   ```bash
   # 开放必要端口
   ufw allow 22/tcp
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw allow 3000/tcp
   ufw --force enable
   ```

## 📁 项目结构说明
```
ai24x-website/
├── api/                    # API接口文件
│   ├── payment.js         # 支付接口
│   ├── share.js           # 分享系统
│   └── fission.js         # 裂变系统
├── css/                   # 样式文件
│   ├── style.css         # 主样式
│   ├── auth.css          # 认证页面样式
│   └── header-fix.css    # 头部修复样式
├── data/                  # 数据文件（JSON格式）
│   ├── ai-tools-data.json    # AI工具数据
│   ├── users.json            # 用户数据
│   └── referral-relations.json # 推荐关系
├── js/                    # JavaScript文件
│   ├── login-enhanced.js  # 增强登录逻辑
│   ├── tools-dynamic.js   # 动态工具加载
│   └── rankings.js        # 排行榜功能
├── templates/             # HTML模板
│   ├── components/        # 组件模板
│   ├── header-unified.html # 统一头部
│   └── footer-unified.html # 统一底部
├── tutorials/             # 教程页面
├── deploy-config/         # 部署配置
│   ├── .env.example      # 环境变量模板
│   ├── deploy.ps1        # 部署脚本
│   └── webhook-handler.js # Gitee Webhook处理器
└── 其他核心文件...
```

## 🔄 数据迁移注意事项

### 1. 用户数据迁移
- 检查 `data/users.json` 格式兼容性
- 验证用户密码哈希算法一致性
- 确认用户等级和权限映射

### 2. 工具数据迁移
- `data/ai-tools-data.json` 包含所有AI工具信息
- 检查工具分类和标签结构
- 验证免费/付费工具标识

### 3. 裂变系统数据
- `data/referral-relations.json` 推荐关系
- `data/invitation-codes.json` 邀请码
- `data/fission-rewards.json` 奖励配置

## 🛡️ 安全配置更新

### 1. 环境变量安全
```bash
# 生成安全的JWT密钥
openssl rand -base64 32 > .env.jwt_secret
JWT_SECRET=$(cat .env.jwt_secret)
```

### 2. 文件权限设置
```bash
# 设置正确的文件权限
chmod 600 .env
chmod 755 server.js
chmod 644 data/*.json
chown -R www-data:www-data .
```

### 3. 数据库备份配置
```bash
# 配置自动备份
crontab -e
# 添加每天2:00备份
0 2 * * * cd /var/www/ai24x-website && node backup-all-files.js
```

## 📈 更新验证清单

### 更新后验证步骤
1. ✅ 网站可访问：http://服务器IP:3000
2. ✅ 首页加载正常，无JavaScript错误
3. ✅ 用户登录/注册功能正常
4. ✅ AI工具页面正常显示和搜索
5. ✅ 支付接口测试（测试模式）
6. ✅ 裂变系统功能验证
7. ✅ 数据库读写正常
8. ✅ 错误日志无异常

### 监控配置
1. **服务状态监控**
   ```bash
   pm2 status ai24x-website
   pm2 logs ai24x-website --lines 50
   ```

2. **性能监控**
   ```bash
   # 检查内存使用
   pm2 monit
   
   # 检查响应时间
   curl -o /dev/null -s -w "Time: %{time_total}s\n" http://localhost:3000
   ```

3. **错误监控**
   ```bash
   # 查看错误日志
   tail -f logs/error.log
   
   # 监控HTTP状态码
   watch -n 5 "netstat -an | grep :3000 | wc -l"
   ```

## 🚨 紧急回滚方案

### 如果更新出现问题，立即执行：
```bash
# 1. 停止当前服务
pm2 stop ai24x-website

# 2. 恢复到备份版本
cd /var/www
rm -rf ai24x-website
cp -r ai24x-website-backup-最新日期 ai24x-website

# 3. 重启服务
cd ai24x-website
pm2 start server.js --name ai24x-website

# 4. 验证回滚
curl -f http://localhost:3000/health || echo "回滚失败，需要人工干预"
```

## 📞 技术支持

### 问题排查流程
1. **检查日志**：`pm2 logs ai24x-website --lines 100`
2. **验证配置**：检查 `.env` 文件和环境变量
3. **测试接口**：使用 `curl` 测试关键API端点
4. **数据库状态**：检查 `data/` 目录文件权限和内容

### 联系支持
- **副脑01（首席开发官）**：负责代码更新和技术支持
- **副脑03（首席网站运维官）**：负责服务器部署和运维
- **飞书协同群**：AI24X五脑协同作战群

## 📊 更新统计
- **总文件数**：211个文件
- **代码行数**：58,834行
- **主要功能模块**：8个（用户系统、工具库、支付、裂变等）
- **部署时间估计**：15-30分钟
- **验证时间估计**：10-15分钟

---

**更新执行人**：副脑01（AI24X首席开发官）  
**更新完成时间**：2026-03-26 16:15 GMT+8  
**下次计划更新**：根据开发进度定期同步  

**口号**：善良正直 + 自主学习 + 团结协助 + 全力以赴 = AI24X成功！