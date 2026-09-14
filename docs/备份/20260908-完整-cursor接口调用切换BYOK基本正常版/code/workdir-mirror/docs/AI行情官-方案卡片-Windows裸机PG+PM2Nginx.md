# AI 行情官｜灯塔版（1.01）方案卡片：Windows 裸机 PostgreSQL + PM2/Nginx

适用：**3 台 Windows Server（副脑01/03/04）**、新人团队、追求**最稳可用 + 最短排障路径**。  
目标：数据库一步到位 PostgreSQL（避免上线后迁库），应用继续 PM2/Nginx（不强推容器化）。

---

## 1) 架构要点（固定）

- **应用**：FastAPI（`p/a/api/server`）由 PM2 管理；前端静态由 Nginx（或静态服务）托管
- **数据库**：每台 Windows Server **裸机安装 PostgreSQL**（服务自启）
- **环境隔离**：三台机器各自独立库，**不共用、不互通**

推荐库名：

- 副脑01（预演）：`ai24x_a_pre`
- 副脑03（国内生产）：`ai24x_a_cn`
- 副脑04（国际生产）：`ai24x_a_intl`

---

## 2) 配置口径（与代码一致）

AI 行情官后端 `.env` 关键项：

```text
AI24X_DB_KIND=pgsql
AI24X_DATABASE_URL=postgresql://ai24x_a:<PASSWORD>@127.0.0.1:5432/ai24x_a_cn
AI24X_JWT_SECRET=<RANDOM>
AI24X_ADMIN_KEY=<RANDOM>
```

应急回滚到 SQLite：

```text
AI24X_DB_KIND=sqlite
AI24X_DB_PATH=./data/ai24x.db
```

---

## 2.1) PostgreSQL 初始化（Windows 裸机，最短可用）

建议统一版本：PostgreSQL 15。

### A. 建用户 + 建库（示例：副脑03 国内生产）

用 `psql`（管理员/超级用户）执行：

```sql
CREATE USER ai24x_a WITH PASSWORD '<PASSWORD>';
CREATE DATABASE ai24x_a_cn OWNER ai24x_a;
GRANT ALL PRIVILEGES ON DATABASE ai24x_a_cn TO ai24x_a;
```

说明：
- **每台机器独立用户/独立库**（预演/生产/国际不要复用同一个库）。
- 连接串里的 host 建议先用 `127.0.0.1`（同机部署最稳），确认跑通后再做远程访问/防火墙放行。

### B. 后端 `.env`（放在 `p/a/api/server/.env`，禁止入 Git）

```text
AI24X_DB_KIND=pgsql
AI24X_DATABASE_URL=postgresql://ai24x_a:<PASSWORD>@127.0.0.1:5432/ai24x_a_cn
AI24X_JWT_SECRET=<RANDOM>
AI24X_ADMIN_KEY=<RANDOM>
```

### C. 首次启动自动建表（无需手动跑迁移）

后端启动时会自动执行 `init_db()` 创建表结构（SQLite/PG 都支持）。

验收最短链路：
- `GET /health` 200
- `account.html` 登录拿到 token
- `demo.html` 查询一次 → `/api/kline` 正常

---

## 3) 备份与回滚（生产强制）

- **生产发布前必做**：`pg_dump` 备份（建议保留 7/30 份，最好异地再存一份）
- **回滚优先级**：
  1) 先回滚代码（最快）
  2) 必要时恢复数据库备份（仅限不可兼容迁移；尽量避免）
  3) PG 故障可临时切回 SQLite（止血用）

---

## 4) 为什么此方案最适合新人

- 少一个体系要学（不引入 Docker/WSL2 容器链路）
- 故障域更清晰（PM2、Nginx、PG 都是标准组件）
- 回滚路径直观（改配置/回退 commit/恢复备份）

