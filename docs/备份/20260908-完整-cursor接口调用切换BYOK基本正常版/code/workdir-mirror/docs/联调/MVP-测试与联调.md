# MVP 测试与联调（首版页面 + 真实链路）

与 `AI24X-Token自由规划-1.0.md` 一致：**本地集成通过 → 副脑 01 预发布 → 新加坡生产**。晚间回归可按下列顺序执行。

## 1. 环境前提

- Python 3.11+（或你当前已跑通 `api/` 的版本）
- PostgreSQL 15（Windows 裸机安装为主；与各项目 `.env` / 初始化建表逻辑一致）
- 仓库路径：`ai24x01/`，静态站由 FastAPI 挂载 `web/`（默认端口见 `api/config`）

## 2. 数据库

```bash
cd db
# 按 db/README 或 docker-compose 启动实例后：
# 执行 schema / 初始化脚本，保证与 models 一致
```

- 确认连接串与 **`api/.env`** 中 `DATABASE_URL`（或项目所用变量名）一致。
- 启动 API 后看日志：**Database initialized successfully**（`main.py` startup）。

若你当前仅需要预览 `web/`（静态站），可以在 `api/.env` 设置：

- `SKIP_DB_INIT=true`

这样 `api` 会跳过数据库初始化并继续提供静态页面（但依赖 DB 的接口自然不可用）。

## 3. 启动 API + 网站（同源）

```bash
cd api
# 激活 venv 后
pip install -r requirements.txt
# 配置 .env 自 .env.example
python main.py
```

- 浏览器：`http://127.0.0.1:8000/`（或你的端口）→ 应加载 `web/index.html`
- Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`GET /health`

## 4. 首版「测试页面」建议路径

| 页面 | 路径 | 用途 |
|------|------|------|
| 控制台 | `console.html` | 已提供：API 基址、Key、`/health`、`/v1/user/info`、`/v1/chat/run` 联调 |
| 首页 | `index.html` | 品牌与入口 |

晚间优先：**控制台填本地 Base → 检测 `/health` → 再测 chat（需有效用户/API Key 或联调 `user_id` 策略）**。

## 5. 常见问题

- **端口占用**：见 `docs/PORT_CONFLICT_SOLUTION.md`
- **仅静态预览**：`cd web && python -m http.server 8080` **无法**代替 API；联调请始终通过 `python main.py` 挂载站点
- **CORS**：本地同源一般无跨域；前端若单独指定 `api.ai24x.com`，以 `web/js/api.js` 与控制台覆盖为准

## 6. 通过标准（首版）

- [ ] `/health` 200  
- [ ] 数据库连接正常、无启动报错  
- [ ] 控制台至少一项请求成功（health 或 user 或 chat，按当时实现）  
- [ ] 关键操作有日志可追溯  

完成后可将同样步骤记一条 **预发布（副脑 01）** 检查项，再晋升新加坡。
