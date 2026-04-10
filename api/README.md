# AI24X 副脑01 API

AI24X副脑01·首席开发官 - 专注于编程相关任务的API服务

## 技术栈
- **后端框架**: FastAPI
- **编程语言**: Python 3.8+
- **数据库**: PostgreSQL
- **缓存**: Redis (可选)
- **部署**: Docker / 原生部署

## 核心功能

### 1. 主要接口
- `POST /v1/chat/run` - 处理聊天请求，自动区分免费/VIP用户

### 2. 用户管理
- 免费用户：每日100次请求，每月3000次请求
- VIP用户：每日1000次请求，每月30000次请求
- 自动速率限制和配额管理

### 3. 请求记录
- 完整记录所有请求和响应
- 统计token消耗和成本
- 性能监控和错误追踪

## 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone <repository-url>
cd ai24x-subbrain01

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库配置
```bash
# 复制环境变量文件
cp .env.example .env

# 编辑 .env 文件，配置数据库连接
# DATABASE_URL=postgresql://user:password@localhost:5432/ai24x_subbrain01
```

### 3. 初始化数据库
```python
# 手动初始化（首次运行）
python -c "from database import init_db; init_db()"
```

### 4. 启动服务
```bash
# 开发模式
python run.py

# 或直接使用uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问API文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 使用示例

### 1. 健康检查
```bash
curl http://localhost:8000/health
```

### 2. 聊天请求（使用API Key）
```bash
curl -X POST http://localhost:8000/v1/chat/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "prompt": "用Python实现一个快速排序算法",
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

### 3. 聊天请求（使用用户ID，测试用）
```bash
curl -X POST "http://localhost:8000/v1/chat/run?user_id=test_user_001" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "解释一下FastAPI的依赖注入",
    "model": "gpt-3.5-turbo"
  }'
```

### 4. 获取用户信息
```bash
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/v1/user/info
```

## 项目结构
```
ai24x-subbrain01/
├── main.py              # 主应用文件
├── config.py           # 配置管理
├── database.py         # 数据库连接
├── models.py          # 数据模型
├── schemas.py         # Pydantic模式
├── services.py        # 业务逻辑
├── requirements.txt   # 依赖包
├── .env.example       # 环境变量示例
├── run.py            # 启动脚本
├── run.bat           # Windows启动脚本
└── README.md         # 说明文档
```

## 开发指南

### 添加新功能
1. 在 `models.py` 中定义数据模型
2. 在 `schemas.py` 中定义请求/响应模式
3. 在 `services.py` 中实现业务逻辑
4. 在 `main.py` 中添加路由端点

### 数据库迁移
```bash
# 初始化迁移
alembic init migrations

# 创建新迁移
alembic revision --autogenerate -m "描述变更"

# 应用迁移
alembic upgrade head
```

### 测试
```bash
# 运行测试
pytest tests/

# 覆盖率报告
pytest --cov=app tests/
```

## 部署

### Docker 部署
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 生产环境配置
1. 使用 `.env` 文件管理敏感配置
2. 启用HTTPS
3. 配置反向代理（Nginx/Apache）
4. 设置监控和日志收集
5. 定期备份数据库

## 故障排除

### 常见问题
1. **数据库连接失败**
   - 检查 `.env` 中的 `DATABASE_URL`
   - 确保PostgreSQL服务正在运行
   - 验证用户名和密码

2. **导入错误**
   - 确保虚拟环境已激活
   - 运行 `pip install -r requirements.txt`

3. **端口被占用**
   - 修改 `.env` 中的 `API_PORT`
   - 检查是否有其他服务使用8000端口

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log
```

## 贡献指南
1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 许可证
MIT License

## 联系方式
- 项目维护: AI24X 副脑01·首席开发官
- 问题反馈: 通过GitHub Issues