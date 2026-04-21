# AI 行情官｜副脑执行指令（最新，可直接转发）

适用：副脑01（预演）、副脑03（国内生产）、副脑04（国际生产）  
部署口径：**Windows 裸机 PostgreSQL + PM2 + Nginx 同域反代**  
域名口径：

- 副脑01：`a1.ai24x.com` → `127.0.0.1:8001`
- 副脑03：`a.ai24x.com` → `127.0.0.1:8001`
- 副脑04：`a4.ai24x.com` → `127.0.0.1:8001`

白名单：**指数 + 浪潮信息（0.000977）**

---

## 0) 执行前约定（强制）

- 仓库根目录：`C:\ai24x01`
- AI 行情官后端目录：`C:\ai24x01\p\a\api\server`
- Nginx 静态根目录：`C:\ai24x01\p\a\web`
- 后端端口：`8001`（仅监听 `127.0.0.1`，由 Nginx 反代对外）
- **生产发布前必须 pg_dump 备份**（副脑03/04 强制；副脑01建议也做）

---

## 1) 一次性准备（每台机器只做一次）

### 1.1 PostgreSQL（本机）

- 安装 PostgreSQL 15（服务自启）
- 建库口径（按环境选择库名）：
  - 副脑01：`ai24x_a_pre`
  - 副脑03：`ai24x_a_cn`
  - 副脑04：`ai24x_a_intl`

示例（以副脑03 为例，用 psql 超级用户执行）：

```sql
CREATE USER ai24x_a WITH PASSWORD '<PASSWORD>';
CREATE DATABASE ai24x_a_cn OWNER ai24x_a;
GRANT ALL PRIVILEGES ON DATABASE ai24x_a_cn TO ai24x_a;
```

### 1.2 后端 `.env`（禁止入 Git）

在 `C:\ai24x01\p\a\api\server\.env` 写入（替换 DB 名与密码）：

```text
AI24X_ENV=prod
AI24X_DB_KIND=pgsql
AI24X_DATABASE_URL=postgresql://ai24x_a:<PASSWORD>@127.0.0.1:5432/ai24x_a_cn
AI24X_JWT_SECRET=<RANDOM>
AI24X_ADMIN_KEY=<RANDOM>
```

### 1.3 Nginx 同域反代（必须）

按模板落地（证书路径/域名替换即可）：`docs/AI行情官-Nginx同域反向代理模板-a1-a-a4.md`

验收：
- `https://<domain>/health` 200
- `https://<domain>/docs` 可打开

---

## 2) 每次发布通用流程（预演/生产都照抄）

> 说明：tag 命名以你们团队实际为准（rc/prod）。这里给“最稳不手滑”的照抄版。

### 2.1 拉取代码并切换版本

```powershell
Set-Location C:\ai24x01
git fetch --tags
# 预演：切 rc tag；生产：切 prod tag
git checkout <TAG_NAME>
```

### 2.2（如依赖有变化）安装后端依赖

```powershell
Set-Location C:\ai24x01\p\a\api\server
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2.3 发布前备份（副脑03/04 强制）

> 建议把备份落到 `D:\backup\ai24x_a\` 并按时间戳命名。

```powershell
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$db = "<DB_NAME>"   # 例如 ai24x_a_cn / ai24x_a_intl / ai24x_a_pre
$out = "D:\backup\ai24x_a\pgdump-$db-$ts.sql"
New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null

& "C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" `
  -h 127.0.0.1 -p 5432 -U ai24x_a -d $db -F p -f $out
```

### 2.4 重启后端（PM2）

> 进程名以实际 PM2 配置为准（建议 `ai24x-a-api`）。

```powershell
Set-Location C:\ai24x01
pm2 list
pm2 restart ai24x-a-api
pm2 save
```

### 2.5 5 分钟验收（必须全部通过）

1) 健康检查：
- `https://<domain>/health` 200

2) API 文档：
- `https://<domain>/docs` 可打开

3) 关键链路：
- 打开 `https://<domain>/account.html` 登录（预演环境 dev code 固定 `1234`；生产按实际短信/邮箱策略）
- 打开 `https://<domain>/demo.html` 查询：
  - 白名单：上证指数 / 北证50 / **浪潮信息（000977）** 其中之一
  - 登录后再查一只非白名单（确认提示/扣次正常）

4) 观察日志（至少看 err）：

```powershell
Set-Location C:\ai24x01
pm2 logs ai24x-a-api --lines 200
```

---

## 3) 回滚（1 分钟级止血版，优先回滚代码）

### 3.1 代码回滚（首选）

```powershell
Set-Location C:\ai24x01
git fetch --tags
git checkout <LAST_GOOD_TAG>
pm2 restart ai24x-a-api
```

验收：`/health`、`/docs`、登录、`demo.html` 查询。

### 3.2 PG 故障止血：切回 SQLite（应急）

在 `C:\ai24x01\p\a\api\server\.env` 改为：

```text
AI24X_DB_KIND=sqlite
AI24X_DB_PATH=./data/ai24x.db
```

然后：

```powershell
pm2 restart ai24x-a-api
```

验收：`/health`、`/docs`、登录、`demo.html` 查询。

---

## 4) 副脑01 / 03 / 04 的“发布铁律”

- 副脑01 预演不通过：禁止进生产（03/04）
- 副脑03/04 发布前：必须 `pg_dump` 备份成功
- 任何故障：优先回滚代码；必要时再恢复 DB

