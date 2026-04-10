## AI24X Token 聚合平台

技术栈：FastAPI + PostgreSQL + 纯 HTML（前端静态页）

### 目录

- `backend/`：FastAPI 后端（含 10 张表 + `POST /v1/chat/run`）
- `frontend/`：登录/注册静态页
- `database/`：PostgreSQL 启动配置（docker-compose）

### 本地运行（推荐：Docker + 虚拟环境）

1) 启动 PostgreSQL

```bash
cd database
docker compose up -d
```

2) 启动后端

```bash
cd ../backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

3) 访问接口文档

- Swagger：`http://127.0.0.1:8000/docs`

### 前端预览

直接打开：

- `frontend/login.html`
- `frontend/register.html`

或用本地服务器（可选）：

```bash
cd frontend
python -m http.server 5173
```

### 测试

```bash
cd backend
pytest -q
```

