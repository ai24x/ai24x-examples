# AI24X Token 聚合平台

## 项目概述
AI24X Token 聚合平台（Token Freedom）是一个全球AI人共创的Token自由平台。

## 技术栈
- 后端：FastAPI + Python
- 数据库：PostgreSQL 15
- 前端：纯 HTML/CSS/JS
- 部署：Docker + Nginx
- 支付：PayPal

## 目录结构
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
├── web/          # 前端网站 (副脑02负责)
│   ├── index.html           # 网站首页
│   ├── login.html           # 登录页面
│   ├── register.html        # 注册页面
│   ├── css/style.css        # 样式文件
│   └── js/main.js           # JavaScript逻辑
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
└── docs/         # 项目文档 (主脑负责)
    ├── api/                 # API文档
    ├── deployment/          # 部署文档
    └── user-guide/          # 用户指南
```

## 核心功能
1. **用户系统**：注册/登录/控制台
2. **API管理**：API Key创建/管理/权限
3. **唯一接口**：`/v1/chat/run` 免费/VIP自动分流
4. **计费系统**：按Token计费 + 余额不足拦截
5. **支付系统**：PayPal充值 + 订单/分成/提现
6. **推荐系统**：二级推荐返利 (10% + 2%)

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

### 3. 前端访问
直接打开 `web/index.html` 或使用本地服务器：
```bash
cd web
python -m http.server 8000
```

## API接口
- 唯一接口：`POST /v1/chat/run`
- 文档地址：`http://localhost:8000/docs` (启动后)

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
AI24X Token 聚合平台 - 版权所有