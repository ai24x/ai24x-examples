## 端口统一规划（生产：副脑03）

目标：让 OpenClaw/实例管理/反代配置“只改一处”，避免端口到处改来改去。

### 0) 核心原则（唯一口径）

- **对外只开放**：`80/443`（HTTPS 走 443），由 Nginx 接管
- **对内固定端口池**：服务只监听 `127.0.0.1`，由 Nginx 反代到对应端口
- **子项目端口双段**：
  - 前端：`1800x`
  - 后端/管理：`1801x`
  - 例：`a1` → 前端 `18001`，后端/管理 `18011`；`fisher` → 前端 `18002`，后端 API `18041`（`ecosystem.local.cjs`：`fisher-api-18041`；数据库 PostgreSQL，见 `p/fisher/api/server/.env.example`）

### 1) 生产端口池（8000+，建议固定）

| 服务 | 域名 | 进程管理 | 监听地址 | 端口 | 备注 |
|---|---|---|---|---:|---|
| 主站静态（www） | `www.ai24x.com` | Nginx | 静态目录 | - | `web/` 直接由 Nginx 托管（不占端口） |
| AI 行情官｜灯塔版（1.01）后端（a） | `a.ai24x.com` | PM2 | `127.0.0.1` | **8001** | 目录：`p/a/api/server`，API 路径：`/api/*`，Docs：`/docs` |
| AI24X 统一 API（api） | `api.ai24x.com` | PM2 | `127.0.0.1` | **8002** | 目录：`api/`，路径：`/*`（含 `/docs`） |
| 山海渔 Fisher API（fisher-api） | `fisher-api.ai24x.com`（建议） | PM2 | `127.0.0.1` | **8003** | 目录：`p/fisher/api/server`（预留），路径：`/*`（含 `/docs`）；建议门面 `fisher.ai24x.com` 与管理端 `fisher-admin.ai24x.com` 走反代 |

> 单机新增项目：依次用 `8003+`，一项目一端口，永远只对内网监听（127.0.0.1），对外统一走 Nginx + HTTPS。

### 1.1) 国际（intl）生产端口池（建议固定一段，避免与 cn 混）

目标：在**同一台**或**不同服务器**上部署 intl 环境时，端口与进程名一眼可区分，避免误重启/误查看日志。

推荐约定：intl 端口池从 **9000+** 起（与 cn 的 8000+ 分段隔离）。

| 服务 | 域名 | 进程管理 | 监听地址 | 端口 | 备注 |
|---|---|---|---|---:|---|
| intl API（api-intl） | `api-intl.ai24x.com`（预留） | PM2 | `127.0.0.1` | **9002** | `api/` 同代码分环境（**分库**、支付/上游/回调配置按 intl）；不对外公布，仅运维/灰度/应急 |
| intl AI 行情官｜灯塔版（a-intl，可选） | `a-intl.ai24x.com` | PM2 | `127.0.0.1` | **9001** | `p/a` 同代码分环境（可后期再上） |

> 约定：对外文档/SDK/示例统一使用 `api.ai24x.com`；`api-cn` / `api-intl` 作为内部预留入口（见 `docs/站点与子项目规划.md` §7.1）。

### 2) 本地开发端口池（18000+，与生产隔离）

| 服务 | 端口 | 说明 |
|---|---:|---|
| 主站（Token自由）API | **8000** | PM2：`core-8000`（含 `/docs`）；对外统一走 Nginx `80/443` |
| AI 行情官 V1.0（a1）前端（p/a1/web） | **18001** | PM2：`a1-web-18001` |
| AI 行情官 V1.0（a1）后端/管理（p/a1/api/server） | **18011** | PM2：`a1-api-18011`（含 `/api/*`、`/docs`、管理后台） |
| 山海渔 Fisher 前端（p/fisher/web） | **18002** | PM2：`fisher-web-18002` |
| 山海渔 Fisher API（p/fisher/api/server） | **18041** | PM2：`fisher-api-18041`；**PostgreSQL**（`FISHER_DATABASE_URL`） |

> 兼容说明：旧版 `p/a` 的 `18001/18031` 属于历史口径；现在以 `p/a1`（V1.0）为准。

### 2.1 常用访问网址（开发/联调最常用）

本地（开发机）：

- 主站（Token自由）API：`http://127.0.0.1:8000/`（Docs：`/docs`）
- AI 行情官 V1.0（a1）前端：`http://127.0.0.1:18001/`
  - 首页：`http://127.0.0.1:18001/index.html`
  - 行情页：`http://127.0.0.1:18001/demo.html`
- AI 行情官 V1.0（a1）后端/管理：`http://127.0.0.1:18011/`
  - 健康检查：`http://127.0.0.1:18011/health`
  - API 文档：`http://127.0.0.1:18011/docs`
  - 行情状态（需 AdminKey）：`http://127.0.0.1:18011/api/status/market-data`
- 山海渔 Fisher 前端（H5 主站）：`http://127.0.0.1:18002/index.html`
- 山海渔 Fisher API：`http://127.0.0.1:18041/`（健康：`/health`，Docs：`/docs`；**需本机 PostgreSQL 已建库**）

生产（服务器，对外域名）：

- AI 行情官 V1.0（a1）前端：`https://a1.ai24x.com/`
- AI 行情官 V1.0（a1）后端（同域反代）：
  - API：`https://a1.ai24x.com/api/`
  - API 文档：`https://a1.ai24x.com/docs`
  - 健康检查：`https://a1.ai24x.com/health`
  - 行情状态（需 AdminKey）：`https://a1.ai24x.com/api/status/market-data`

说明：

- 管理后台与状态接口使用 `X-Admin-Key` 鉴权，对外部署时建议仅管理员可访问或加额外限制（IP 白名单/基础认证等）。
- `p/a1/web/*.html` 在本地运行于 `127.0.0.1:18001` 时，会自动把 API 指向 `127.0.0.1:18011`（便于联调）。

### 2.2 AI 行情官｜灯塔版（1.01）：后台配置怎么填（简要）

入口：

- 本地：先打开 `http://127.0.0.1:18031/` 看 JSON；默认管理登录 `http://127.0.0.1:18031/admin20260501/login`；与日期前缀并存时也可用 **`http://127.0.0.1:18031/admin`** / **`/admin/login`**（同一套页面，需拉取新代码并重启进程）
- 生产：与部署时 `AI24X_ADMIN_MOUNT_PATH` 一致（默认示例 `https://a.ai24x.com/admin20260501/login`）

鉴权：

- 页面可直接打开；但**保存/读取配置**会调用受保护接口，需要在后台页面里填写 **AdminKey**（对应请求头 `X-Admin-Key`）。

最常用配置项（key/value）：

- **`paid_provider`**：付费源开关与选择
  - `off`：关闭付费源（此时即使优先级里写了 `paid` 也会跳过，转向腾讯/东财/新浪等公共源）
  - `tushare`（或 `ts`）：启用 TuShare Pro 作为付费源
- **`paid_provider_priority`**：数据源优先级（逗号分隔）
  - 示例（付费优先）：`paid,tencent,eastmoney,sina`
  - 示例（公共优先）：`tencent,eastmoney,sina,paid`
  - 说明：当这里**显式以 `paid` 开头**时，视为“强制付费优先”（便于公共源被限流时应急切流）
- **`paid_vip_only`**：是否仅 VIP 允许走付费源
  - `0/false/off`：所有用户都允许在必要时回落到付费源
  - `1/true/on`：仅 VIP 可用付费源（免费用户只走公共源）
- **`tushare_use_rt_k`**：是否尝试 `rt_k`（不建议常开）
  - `0`：默认（推荐，用 `daily + adj_factor`）
  - `1`：允许尝试 `rt_k`（该接口可能有非常严格的频率限制）

生效方式：

- 保存后通常 **5 秒内**生效（后端有轻量缓存）；要立刻生效可重启：`pm2 restart a-api`

### 3) Nginx 反代固定映射（同域最省心）

- `a1.ai24x.com/` → `http://127.0.0.1:18001/`
- `a1.ai24x.com/api/*` → `http://127.0.0.1:18011/api/*`
- `a1.ai24x.com/docs` → `http://127.0.0.1:18011/docs`

- `a.ai24x.com/` → 静态目录：`p/a/web/`
- `a.ai24x.com/api/*` → `http://127.0.0.1:8001/api/*`
- `a.ai24x.com/docs` → `http://127.0.0.1:8001/docs`

- `api.ai24x.com/*` → `http://127.0.0.1:8002/*`

### 4) PM2 固定进程名（便于实例管理一键重启）

见仓库根目录 `ecosystem.config.cjs`：

- `a-api-8001` → 8001
- `core-api-8002` → 8002

intl 建议命名（避免与 cn 混淆）：

- `ai24x-intl-core-api` → 9002
- `ai24x-intl-a-api` → 9001（可选）

### 5) 本地用 PM2 管理（推荐：不再混淆 cmd）

> 前提：已安装 Node.js + PM2（`npm i -g pm2`）

本地开发建议使用仓库根目录的 `ecosystem.local.cjs`（Windows 友好，端口不变）。

**Windows 实测注意**：PM2 在 Windows 下可能不会把 `ecosystem.local.cjs` 识别为“配置文件”而是当脚本执行。为避免歧义，使用同目录的 **`ecosystem.local.config.js`** 启动（它只是 `require("./ecosystem.local.cjs")` 的别名入口）。

进程名与端口速查（本地）：

| PM2 进程名 | 端口 | 常用访问 |
|---|---:|---|
| `core-8000` | **8000** | `http://127.0.0.1:8000/`（健康：`/health`，Docs：`/docs`） |
| `a1-web-18001` | **18001** | `http://127.0.0.1:18001/` |
| `a1-api-18011` | **18011** | `http://127.0.0.1:18011/`（健康：`/health`，Docs：`/docs`） |
| `fisher-web-18002` | **18002** | `http://127.0.0.1:18002/index.html` |
| `fisher-api-18041` | **18041** | `http://127.0.0.1:18041/docs`（PostgreSQL + `FISHER_DATABASE_URL`） |

```powershell
cd "E:\AI24X\ai24x-website\ai24x01"
pm2 start ecosystem.local.config.js
pm2 status
pm2 logs core-8000
pm2 logs a1-api-18011
pm2 logs a1-web-18001
pm2 logs fisher-api-18041
pm2 logs fisher-web-18002
```

常用：

- 重启 API：`pm2 restart a1-api-18011`
- 重启 Fisher API：`pm2 restart fisher-api-18041`（需本机 PostgreSQL）
- 停止全部：`pm2 stop a1-api-18011 a1-web-18001`
- 删除进程：`pm2 delete a1-api-18011 a1-web-18001`
- 全部停止/删除（含主站）：`pm2 stop core-8000 a1-api-18011 a1-web-18001` / `pm2 delete core-8000 a1-api-18011 a1-web-18001`

说明：

- `core-8000`：主站 + AI24X 统一 API（本地 `8000`）
- `a1-web-18001`：AI 行情官 V1.0（a1）静态页（本地 `18001`）
- `a1-api-18011`：AI 行情官 V1.0（a1）后端/管理（本地 `18011`）
- `fisher-web-18002`：山海渔 H5（本地 `18002`）
- `fisher-api-18041`：山海渔 API（本地 `18041`，**PostgreSQL**）

