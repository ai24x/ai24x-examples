# 山海渔（ShanHai Fisher）— 子项目 `p/fisher`

对外长期品牌：**山海渔**（ShanHai Fisher）。前期小程序展示名、商标与审核策略以法务与微信侧为准。

## 文档入口（已汇总落盘）

- **[产品规划（完整版 v1.0）](docs/产品规划-山海渔-完整版-v1.0.md)**：品牌、玩法、数值、动效、阶段、合规与盈利（含工程优化说明）。
- **[架构与落地汇总（优化版）](docs/架构与落地汇总.md)**：域名与证书、API-first 真源、目录约定、阶段里程碑、与主站/行情官是否统一身份。
- **[文档与记忆存放约定](docs/文档与记忆存放约定.md)**：`docs` 与仓库根目录 `memory/` 如何分工。
- **[开发推进流程](docs/开发推进流程.md)**：先 API、再小程序；网页 Demo 何时做。
- [文档索引](docs/README.md)

**决策**：`memory/decisions/DEC-0009-山海渔-Fisher身份默认独立与真源边界.md`

## 在本仓库中的位置

- 本目录：`p/fisher/`，与 `p/a/`（AI 行情官）同级，遵循 `p/README.md` 的「一项目一目录」约定。

## 推荐目录（按需创建）

| 路径 | 用途 |
|------|------|
| `miniprogram/` | 微信原生小程序（开发者工具打开本目录） |
| `api/server/` | Fisher 自建后端（真源）；**本地默认端口 `18041`** |
| `api/server/data/` | SQLite 文件目录（`fisher.db` 由运行时创建，已 `.gitignore`） |
| `web/` | H5 主站 `index.html`（海王·山海渔）；`bag.html` 仓库；旧联调封存 `archive/history-legacy.html`；本地默认 `18002` |
| `docs/` | 架构、数值、合规与版本记录 |
| `scripts/` | 启动脚本（`start_api.cmd`） |

**PM2（仓库根）**：`ecosystem.local.cjs` 已增加进程 **`fisher-api-18041`**、**`fisher-web-18002`**（与 `a-api-18031` 并列）。

## 技术路线（当前口径）

- **客户端**：微信原生；动效以 CSS 为主，`transform` 优先。  
- **真源**：`fisher-api.*` 自建服务 + PostgreSQL（详见 `docs/架构与落地汇总.md`）。  
- **微信云开发**：可选辅助，**不作为**经济系统的长期唯一真源。  
- **多端框架（Taro 等）**：待 H5/App 与小程序同周迭代时再评估。

## 与主站 / 行情官

- **游戏数据**：默认 **不** 写入主站 `api/` 业务库；经济真源在 Fisher 库。  
- **账号是否统一**：可选；若需「全站一个 AI24X 账号」，则对齐 `memory/decisions/DEC-0007-身份真源-api与行情官认票.md` 中的身份契约，并建议另起 DEC 固化 Fisher 侧字段与边界。  
- **可复用经验**：PM2、Nginx、管理后台密钥基线等 —— 见 `docs/架构与落地汇总.md` 第六节路径索引。

## 忽略规则

见仓库根 `p/fisher/.gitignore`（含 `project.private.config.json` 等）。
