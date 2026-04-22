## a.ai24x.com（AI 行情官｜灯塔版（1.01））最小部署步骤

目标：先让 `a.ai24x.com` 7×24 可用（静态页 + API 同域），后续再增强监控/缓存/支付。

### 1) 端口约定

- 生产服务端口：**8001**
- 本地开发端口：静态 18001，API 18031（以本仓库文档为准）

### 2) 静态文件

部署静态目录（建议同域）：

- `p/a/web/`（至少包含 `index.html`、`demo.html`）
- `p/a/vendor/`（可选，图表库本地优先）

### 3) 后端 API

启动后端（示例）：

```bash
cd p/a/api/server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

数据库口径（与当前拍板一致）：

- **生产**建议直接使用 **Windows 裸机 PostgreSQL**（并保留可随时切回 SQLite 的开关）
- 环境变量示例见：`p/a/api/server/.env.example`（`AI24X_DB_KIND` / `AI24X_DATABASE_URL`）
- 统一发布/回滚卡片见：
  - `docs/AI行情官-统一主方案-按阶段按步骤.md`
  - `docs/AI行情官-方案卡片-发布总流程最精简不出错.md`

### 4) 反向代理（同域）

反代建议（概念）：

- `a.ai24x.com/` → 静态根（`p/a/web/`）
- `a.ai24x.com/api/*` → `http://127.0.0.1:8001/api/*`
- `a.ai24x.com/docs` → `http://127.0.0.1:8001/docs`

> 好处：前端 `API_BASE=''` 即同域调用，跨域问题最少。

### 5) 最小验收

- 打开 `a.ai24x.com/index.html` 能登录（dev 阶段验证码机制按配置）
- 进入 `demo.html` 顶部栏能显示“日/周剩余”
- 查询成功后剩余次数下降（30 秒内重复不应快速下降）

