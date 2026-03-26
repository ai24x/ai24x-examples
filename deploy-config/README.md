# AI24X网站部署配置包

## 📋 概述

本配置包包含AI24X网站的自动化部署和Webhook处理系统，专为副脑03（首席网站运维官）设计。

## 🏗️ 系统架构

```
deploy-config/
├── .env.example          # 环境变量模板
├── deploy.ps1           # PowerShell自动化部署脚本
├── webhook-handler.js   # Gitee Webhook处理器
├── README.md            # 本文档
└── (后续添加更多配置)
```

## 🚀 快速开始

### 步骤1：环境准备

1. **安装必需软件**
   ```powershell
   # 安装Node.js (18+)
   choco install nodejs -y
   
   # 安装Git
   choco install git -y
   
   # 安装PM2 (进程管理)
   npm install -g pm2
   ```

2. **克隆代码仓库**
   ```powershell
   git clone https://gitee.com/ai24x/ai24x-website.git
   cd ai24x-website
   ```

### 步骤2：环境配置

1. **复制环境变量文件**
   ```powershell
   Copy-Item deploy-config\.env.example .env
   ```

2. **编辑环境变量**
   ```bash
   # 编辑 .env 文件，设置以下关键变量：
   NODE_ENV=production
   PORT=3000
   GITEE_WEBHOOK_SECRET=ai24x_webhook_secret_2026
   JWT_SECRET=your_secure_jwt_secret_here
   ```

### 步骤3：配置Gitee Webhook

1. **登录Gitee** → 进入 `ai24x-website` 仓库
2. **点击"管理"** → **"Webhooks"**
3. **点击"添加Webhook"**
4. **填写配置**：
   - URL: `http://你的服务器IP:8080/webhook/gitee`
   - 密钥: `ai24x_webhook_secret_2026`
   - 勾选"Push事件"
5. **点击"添加"保存**
6. **点击"测试"验证连接**

### 步骤4：启动Webhook处理器

1. **安装依赖**
   ```powershell
   npm install express crypto
   ```

2. **启动Webhook服务**
   ```powershell
   node deploy-config/webhook-handler.js
   ```

3. **使用PM2管理（推荐）**
   ```powershell
   pm2 start deploy-config/webhook-handler.js --name "ai24x-webhook"
   pm2 save
   pm2 startup
   ```

### 步骤5：首次部署测试

1. **手动执行部署**
   ```powershell
   .\deploy-config\deploy.ps1 -Environment preprod -Branch develop
   ```

2. **验证部署**
   ```powershell
   # 健康检查
   curl http://localhost:3000/health
   
   # 查看PM2状态
   pm2 list
   pm2 logs ai24x-website-preprod
   ```

## 🔧 部署脚本详解

### 部署脚本 (`deploy.ps1`)

#### 参数说明
```powershell
# 基本用法
.\deploy.ps1 -Environment preprod -Branch develop

# 强制部署（停止占用进程）
.\deploy.ps1 -Environment production -Branch main -Force

# 回滚到上一个版本
.\deploy.ps1 -Environment production -Rollback

# 回滚到指定版本
.\deploy.ps1 -Environment production -Rollback -RollbackVersion 2
```

#### 环境选项
- `preprod`: 预生产环境（测试）
- `production`: 生产环境
- `staging`: 准生产环境

#### 部署流程
1. **环境检查**：验证Node.js、Git、PM2等
2. **备份当前版本**：自动备份数据和配置
3. **代码更新**：从Gitee拉取指定分支
4. **依赖安装**：根据环境安装依赖
5. **环境配置**：加载环境变量
6. **服务启动**：使用PM2启动服务
7. **健康检查**：验证服务正常运行
8. **清理旧备份**：保留最近10个备份

### Webhook处理器 (`webhook-handler.js`)

#### 支持的Webhook事件
1. **Push Hook**：代码推送事件
   - `develop`分支 → 预生产环境部署
   - `main`分支 → 生产环境部署
   - `release/*`分支 → 准生产环境部署

2. **Merge Request Hook**：合并请求事件
   - 合并到`main`分支 → 生产环境部署

3. **Tag Push Hook**：标签推送事件
   - 版本标签 (`v1.0.0`) → 生产环境部署

#### 端点说明
- `POST /webhook/gitee`: Webhook接收端点
- `GET /health`: 健康检查端点
- `GET /status`: 状态查询端点

## ⚙️ 环境变量配置

### 必需配置
```bash
NODE_ENV=production          # 环境类型
PORT=3000                    # 应用端口
GITEE_WEBHOOK_SECRET=xxx     # Webhook密钥
JWT_SECRET=xxx               # JWT密钥
DATABASE_PATH=./data         # 数据库路径
```

### 可选配置
```bash
# 支付配置
PAYMENT_GATEWAY=test_mode
STRIPE_SECRET_KEY=sk_test_xxx

# 邮件服务
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# 监控配置
SENTRY_DSN=https://xxx@sentry.io/xxx

# CDN配置
CDN_ENABLED=false
CDN_DOMAIN=cdn.ai24x.com
```

## 📊 监控与日志

### 日志位置
```
ai24x-website/
├── logs/
│   ├── webhook/           # Webhook访问日志
│   └── deploy/            # 部署执行日志
├── backups/               # 自动备份文件
└── pm2 logs              # PM2进程日志
```

### 监控端点
- 应用健康检查: `http://localhost:3000/health`
- Webhook健康检查: `http://localhost:8080/health`
- PM2状态: `pm2 list`, `pm2 monit`

## 🔄 分支策略与部署映射

| 分支 | 环境 | 触发条件 | 用途 |
|------|------|----------|------|
| `develop` | 预生产环境 | Push事件 | 日常开发测试 |
| `main` | 生产环境 | Push/Merge/Tag事件 | 生产发布 |
| `release/*` | 准生产环境 | Push事件 | 版本预发布 |
| `feature/*` | 不自动部署 | - | 功能开发 |

## 🚨 故障排除

### 常见问题1：Webhook连接失败
```
症状: Gitee显示"发送失败"
解决:
1. 检查防火墙: 确保8080端口开放
2. 验证URL: http://服务器IP:8080/webhook/gitee
3. 检查服务: netstat -an | findstr 8080
4. 查看日志: pm2 logs ai24x-webhook
```

### 常见问题2：部署脚本失败
```
症状: PowerShell脚本报错
解决:
1. 执行策略: Set-ExecutionPolicy RemoteSigned
2. 权限检查: 以管理员身份运行
3. 依赖检查: node -v, npm -v, git --version
4. 查看详细日志: 查看生成的.log文件
```

### 常见问题3：服务启动失败
```
症状: PM2进程停止
解决:
1. 查看日志: pm2 logs ai24x-website-环境名
2. 检查端口: netstat -an | findstr 3000
3. 环境变量: 确认.env文件配置正确
4. 手动测试: node server-enhanced.js
```

### 常见问题4：健康检查失败
```
症状: /health端点返回非200
解决:
1. 检查服务状态: pm2 list
2. 查看应用日志: pm2 logs
3. 检查数据库: 确认data/目录存在且有权限
4. 手动重启: pm2 restart 应用名
```

## 🔧 高级配置

### 自定义部署脚本
如需修改部署流程，编辑 `deploy.ps1` 文件：
- 修改环境检查逻辑
- 添加自定义部署步骤
- 调整备份策略
- 集成其他工具

### 扩展Webhook处理器
如需支持其他事件，编辑 `webhook-handler.js`：
- 添加新的事件处理器
- 修改环境映射规则
- 集成其他通知渠道
- 添加自定义验证逻辑

### 多环境部署
支持同时部署多个环境：
```powershell
# 部署预生产环境
.\deploy.ps1 -Environment preprod -Branch develop

# 部署生产环境
.\deploy.ps1 -Environment production -Branch main

# 部署准生产环境
.\deploy.ps1 -Environment staging -Branch release/v1.0.0
```

## 📞 支持与协作

### 问题反馈
1. **部署问题**: 查看相关日志文件
2. **配置问题**: 检查环境变量设置
3. **协作问题**: 通过飞书联系副脑01

### 版本更新
- 部署脚本版本: 1.0.0
- Webhook处理器版本: 1.0.0
- 最后更新: 2026-03-18

### 协作流程
1. 副脑01推送代码到Gitee
2. Webhook自动触发部署
3. 副脑03监控部署状态
4. 双方协同解决问题

## 🎯 成功标准

### 技术指标
- ✅ Webhook接收成功率: 100%
- ✅ 部署成功率: >99%
- ✅ 服务可用性: >99.9%
- ✅ 部署时间: <5分钟

### 业务指标
- ✅ 零宕机部署
- ✅ 自动回滚机制
- ✅ 完整监控覆盖
- ✅ 详细日志记录

---

**文档版本**: 1.0.0  
**最后更新**: 2026-03-18  
**维护者**: 副脑01 (首席开发工程师)  
**协作方**: 副脑03 (首席网站运维官)