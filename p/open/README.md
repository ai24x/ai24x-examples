# AI24X—AI 无限 · 接口自由，一站式多模型 API 与智能应用服务平台

## 项目概述
AI24X—AI 无限 · 接口自由，是一个全球 AI 人共创的一站式多模型 API 与智能应用服务平台。

> **BYOK 智能网关（2026-08-18，Phase 1）**：open.ai24x.com 正从「Token 聚合转售」
> 改造为「用户自带 Key（Bring Your Own Key）多模型智能网关」——用户自备上游 key，
> 平台只做技术转发 + 智能路由 + 故障转移 + 请求缓存 + 用量/成本看板，收平台服务费，
> 不囤 token、不赚差价、封号风险归零。详见 [`docs/BYOK-网关改造说明-2026-08-18.md`](docs/BYOK-网关改造说明-2026-08-18.md)。

> **当前升级方向（2026 国内优先验证）**：本仓库同时承载主站 `www.ai24x.com`、核心 API `api.ai24x.com`，以及可持续追加的新项目池 `p/`（第一个子项目：**AI 行情官｜灯塔版（1.01）**：`a.ai24x.com`）。  
> **文档入口**：先打开 [`docs/README.md`](docs/README.md)。Token 总纲：[`docs/规划/开发总纲-AI24X-API-v3.5.md`](docs/规划/开发总纲-AI24X-API-v3.5.md)。站点规划：[`docs/规划/站点与子项目规划.md`](docs/规划/站点与子项目规划.md)。

## 技术栈
- 后端：FastAPI + Python
- 数据库：PostgreSQL 15
- 前端：纯 HTML/CSS/JS
- 部署：Docker + Nginx
- 支付：微信、支付宝、PayPal

## 目录结构（按最新规范）
```
ai24x01/
├── api/          # 后端接口 (副脑01负责)
│   ├── main.py              # FastAPI主程序
│   ├── config.py            # 配置管理
│   ├── models.py            # 数据模型
│   ├── schemas.py           # Pydantic模型
│   ├── services.py          # 业务逻辑
│   ├── database.py          # 数据库连接
│   ├── requirements.txt     # Python依赖
│   ├── .env.example         # 环境变量示例
│   ├── docker-compose.yml   # Docker配置
│   ├── deploy.ps1           # Windows部署脚本
│   ├── deploy.sh            # Linux部署脚本
│   └── test_api.py          # API测试
├── web/          # 前端官网（纯 HTML/CSS/JS）
│   ├── index.html           # 首页 + 8 个业务页 + 登录/注册
│   ├── css/base.css         # 布局与组件基础
│   ├── css/themes/          # 三套皮肤：蓝白 / 深色商务 / 轻量卡片
│   ├── config/locales.js    # 中/英/日/韩/德/法/西 文案
│   ├── js/api.js            # 统一请求封装（默认生产 api.ai24x.com）
│   ├── js/shell.js          # 公共页眉页脚
│   ├── js/i18n.js + app.js
│   └── start_web.bat        # 进入 api 同端口 :8000
├── db/           # 数据库 (副脑04负责)
│   ├── schema.sql           # 表结构SQL
│   ├── connection.txt       # 数据库连接信息
│   └── setup.sh             # 数据库初始化脚本
├── config/       # 项目配置 (主脑负责)
│   ├── .env.example         # 环境变量示例
│   └── requirements.txt     # 基础依赖
├── scripts/      # 运维脚本 (副脑03/04负责)
│   ├── deploy/              # 部署脚本
│   ├── monitor/             # 监控脚本
│   └── backup/              # 备份脚本
├── p/            # 子项目池（可持续追加：独立迭代/独立部署）
└── docs/         # 项目文档 (主脑负责)
    ├── AI24X-Token自由规划-1.0.md  # 顶层规划
    ├── MVP-测试与联调.md          # 首版：DB + API + 控制台测试步骤
    ├── README.md                  # 文档索引（勿在公开文档写令牌）
    ├── archive/legacy-reports/    # 历史报告归档（不参与当前决策）
    ├── api/                       # API 文档（如有）
    ├── deployment/                # 部署文档（如有）
    └── user-guide/                # 用户指南（如有）
```

## 核心功能
1. **用户系统**：注册/登录/控制台
2. **API管理**：API Key创建/管理/权限
3. **唯一接口**：`/v1/chat/run` 免费/VIP自动分流
4. **计费系统**：按Token计费 + 余额不足拦截
5. **支付系统**：微信、支付宝、PayPal 充值 + 订单/分成/提现
6. **推荐系统**：二级推荐返利 (10% + 2%)

## 文档与首版测试

- **顶层规划**：`docs/AI24X-Token自由规划-1.0.md`
- **文档索引**：`docs/README.md`
- **站点与子项目规划**：`docs/站点与子项目规划.md`（`www/api/a` 子域分层 + `p/` 扩展方式）
- **晚间联调清单（DB + 真实 API）**：`docs/MVP-测试与联调.md`
- **主脑实训（每日任务 + 复盘）**：`docs/training/README.md`（目录索引）· `docs/training/AI24X-主脑实训路线.md`
- **静态站说明**：`web/README.md`

## 快速开始

### 1. 数据库启动
```bash
cd db
docker compose up -d
```

### 2. 后端启动
```bash
cd ../api
python -m venv .venv
.\.venv\Scripts\activate  # Windows
pip install -r requirements.txt
copy .env.example .env    # 配置环境变量
python main.py
```

若你当前只想让主站页面能跑（不连接数据库），可在 `api/.env` 设置：

- `SKIP_DB_INIT=true`

### 3. 前端访问（与 API 同端口 8000）
启动 `api` 后，静态站点由 FastAPI 挂载 `web/`，与接口共用 **8000**：

- 首页：`http://localhost:8000/` 或 `http://localhost:8000/index.html`
- 控制台（联调）：`http://localhost:8000/console.html`
- Swagger：`http://localhost:8000/docs`
- 语言：页眉语言选择器切换（`web/config/locales.js`）

本地可双击仓库根目录 `start_local.bat`，或运行 `web/start_web.bat`（内部会进入 `api` 并执行 `python main.py`）。

**Windows 登录后自动恢复 PM2 进程（可选）**：先至少成功运行一次 `start_local.bat`，再在仓库根执行 `pm2 save`；然后一次性执行 `powershell -ExecutionPolicy Bypass -File .\scripts\register-pm2-local-login.ps1`（会注册计划任务 `AI24X-PM2-Local-Dev`，登录时运行 `pm2 resurrect`）。取消：`schtasks /delete /tn "AI24X-PM2-Local-Dev" /f`。

仅静态预览且不接 API 时，可另开终端：`cd web` 后 `python -m http.server 8000`（此时不要同时占用 8000 起 API）。

## API接口
- 生产统一地址：`https://api.ai24x.com/v1/chat/run`
- 路径与方法：`POST /v1/chat/run`
- 本地 Swagger：`http://localhost:8000/docs`（启动 `api` 后）

## 开发规范
1. **目录规范**：严格按上述结构存放文件
2. **代码规范**：中文注释，英文标识
3. **提交规范**：清晰描述修改内容
4. **测试规范**：所有功能必须测试

## 分工负责
- **主脑**：整体架构、目录规划、权限管理
- **副脑01**：`api/` 全部后端接口开发
- **副脑02**：`web/` 全部前端页面开发
- **副脑03**：`scripts/` 国内运维脚本
- **副脑04**：`db/` 数据库 + 新加坡服务

## 许可证
AI24X—AI 无限 · 接口自由 - 版权所有
