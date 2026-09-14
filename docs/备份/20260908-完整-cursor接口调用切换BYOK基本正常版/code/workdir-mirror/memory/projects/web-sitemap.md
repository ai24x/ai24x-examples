# AI24X Web 站点地图

> 扫描日：2026-08-26｜只读盘点  
> 活跃 web 根共 **5** 个；`p/a` 等早期站已迁出归档。

---

## 0. 仓库根一级（一句话）

| 目录 | 用途 |
|------|------|
| `api/` | 主站 Token / 核心平台后端（`api.ai24x.com`） |
| `web/` | 主站静态前端（`www.ai24x.com`） |
| `p/` | 子项目池（独立部署：open / markets / a1 / game…） |
| `db/` | 主库 schema、迁移、部分 nginx 样例 |
| `docs/` | 规划、联调、营销收发、帮助知识库 |
| `ops/` | 部署探针、验收脚本、SEO/社媒草稿与日志 |
| `scripts/` | 本机运维、文案检查、部署辅助 |
| `config/` | 仓库级示例配置（非生产密钥） |
| `memory/` | 作战卡 / 决策 / 项目记忆 |
| `收发/` | 平台官 / 行情官 与总司令文件通道 |
| `ecosystem*.{js,cjs}` | PM2 本地/生产进程编排 |

---

## 1. `web/` — 主站 Token 平台

**定位**：`www.ai24x.com` 多模型 API / Token 聚合出口官网 + 控制台（纯 HTML/CSS/JS，无构建）。

### 顶层 HTML（按用户路径）

| 分组 | 页面 |
|------|------|
| 营销 | `index.html` `product.html` `pricing.html` `partner.html` `about.html` `refer.html` `demo.html` |
| 鉴权 | `login.html` `register.html` `forgot.html` |
| 控制台 / 账户 | `console.html` `dashboard.html` `account.html` `status.html` `paypal.html` |
| 帮助 / 文档 | `help.html` `docs.html` `api.html` |
| 合规 | `terms.html` `privacy.html` |
| SEO / 内容子树 | `guides/` `models/` `blog/` + `sitemap.xml` `robots.txt` |
| 运维 / 内部（勿当用户主路径） | `token-admin.html` `command-center.html` `ai24x.html` `AI行情官.灯塔版V1.0{2,3}.html` `404.html` |

### 子目录

| 路径 | 用途 |
|------|------|
| `css/` `css/themes/` | `base.css`；主题 `theme-blue` / `theme-dark` / `theme-cards` |
| `js/` | `shell.js` 页眉页脚；`api.js`→默认 `https://api.ai24x.com`；`i18n.js` `i18n-boot.js` `app.js` `console.js` `invite.js` `utm.js` `support-widget.js` |
| `config/` | **`locales.js`**（多语文案真源）；`consent.js` |
| `guides/` | 接入指南（Cursor/Codex/n8n/OpenClaw…）；含 `openrouter-migration` / `openrouter-vs-ai24x` |
| `models/` | 模型落地页（kimi / deepseek / qwen / mimo…） |
| `blog/` | 博客索引与文章 |
| `ops/` | `ai24x-command.json`（指挥台数据，非公网营销） |
| `scripts/` | `bump_asset_version.py`（`?v=` 缓存破除） |

### 关键静态入口

- 文案：`web/config/locales.js`
- 壳层：`web/js/shell.js` + `css/base.css` + `css/themes/theme-*.css`
- API：`web/js/api.js`（生产默认 `api.ai24x.com`）

### 关系

- 与 `p/open/web/` **近镜像**；主站走 **Token 转售 / 统一账号**，API 指向 core。
- 与行情产品解耦：行情在 `p/a1`、`p/markets`；本目录内「灯塔版」HTML 为遗留/内部页。

---

## 2. `p/open/web/` — 开放站 BYOK 网关

**定位**：`open.ai24x.com` — 由 Token 镜像演化为 **用户自带 Key（BYOK）多模型智能网关** 前端；自有 `p/open/api`，账号与 www/core **隔离**。

### 顶层 HTML

与 `web/` 基本同构（营销 / 鉴权 / console / help / 合规 / guides / models / blog）。

**相对主站差异（文件层）**：

- 缺根页 `api.html`
- `guides/` 缺 `openrouter-migration.html`、`openrouter-vs-ai24x.html`
- 其余页面集合基本对齐（含 `token-admin`、灯塔遗留页）

### 子目录 / 关键入口

与主站同构：`css/` `js/` `config/locales.js` `guides/` `models/` `blog/` `ops/` `scripts/`。

- **`js/api.js` 硬差异**：主机名为 `open.ai24x.com` 时 **强制同源 API**，禁止落到 `api.ai24x.com`。

### 关系

- **结构镜像 + 产品分叉**：UI 同源拷贝；后端 / 计费 / 账号独立（BYOK 服务费，不囤 Token）。
- 改主站文案/页面时，open 需按需同步，勿默认「一改两边」。

---

## 3. `p/markets/web/` — 行情官国际版

**定位**：`markets.ai24x.com` — 英文美股/ETF/指数：图表 + 技术指标 + AI 描述性点评；订阅 + PayPal；合规「出版例外」。

### 顶层 HTML

| 分组 | 页面 |
|------|------|
| 营销 / 落地 | `index.html` `pricing.html` |
| 产品 App | `app.html`（主工具）`screener.html` |
| 合规 | `privacy.html` `tos.html` |
| 内容 | `daily/index.html` |
| SEO | `seo/`（个股页 + 指标/对比指南）+ `sitemap.xml` `robots.txt` |
| PWA | `manifest.webmanifest` `sw.js` `icons/` |

### 子目录

| 路径 | 用途 |
|------|------|
| `seo/` | 个股落地（nvda/aapl/…）+ `*-guide.html` + ETF 对比页 + `assets/*.svg` |
| `daily/` | 日报类内容入口 |
| `vendor/` | `lightweight-charts` 本地化 |
| 根级 JS | `help-widget.js`（无主站式 `shell.js` / `locales.js`） |

### 关键静态入口

- 无统一 `locales.js` / `shell.js`（英文产品页内联样式+脚本为主）
- 图表：`vendor/lightweight-charts.standalone.production.js`
- SEO 批量页：`seo/*.html`

### 关系

- **非** `web/` 镜像；与 `p/a1` 同属行情产品线但 **市场/语言/支付/合规分离**（国际 vs A 股国内）。
- 账户/支付能力约定共享核心层，前端独立部署（副脑 04）。

---

## 4. `p/a1/web/` — 行情官国内 / A1

**定位**：`a.ai24x.com` — A 股 K 线智能标注 / 技术形态工具（灯塔版现行工程）；中文；国内支付/配额。

### 顶层 HTML

| 分组 | 页面 |
|------|------|
| 产品主路径 | `index.html`（正式入口）`demo.html`（基线备份）`account.html` |
| 工具 | `gd.html`（复盘/扫描 VIP）`watchscore.html` |
| 营销 / 合作 | `partner.html` |
| 帮助 / 反馈 | `help.html` `feedback.html` |
| 合规 | `terms.html` `privacy.html` |
| 移动端 | `m.html` + **`m/`**（`index` `quote` `daily` `gd` `account` `help` `feedback`） |
| 日报 / 研究 | `daily/`（`index` `view` `gd`）`bj/`（北证跟踪本地页） |
| 其它 | `sitemap.xml` `robots.txt` `sw.js` |

### 子目录

| 路径 | 用途 |
|------|------|
| `css/` `css/themes/` | `base.css` `tool.css` `bjscreener.css` `watchscore.css` + 三主题 |
| `js/` | **`shell.js`**（轻量页眉页脚；本地 `:18001`→API `:18011`）；`bjscreener.js` `watchscore.js` `theme.js` |
| `m/` | 手机版页面 + `m/css` `m/js` |
| `daily/` `bj/` | 日报与北证扫描工具页 |
| `vendor/` | lightweight-charts |
| `logs/` | 本地 QA/PM2 日志（非产品） |

### 关键静态入口

- `js/shell.js` + `css/base.css` + `css/themes/*`
- **无** `config/locales.js`（中文写死 / 页内文案）
- 本地：静态 `18001`，API `18011`

### 关系

- 现行真源；`p/a` 已封存（见 `memory/projects/a.md`）。
- 与 `markets` 平行产品；与主站 Token 仅品牌/账号策略相关，前端树独立。

---

## 5. `p/game/fisher/web/` — 山海渔 H5

**定位**：互动小游戏矩阵样版「海王 · 山海渔」H5（垂钓→卖鱼→升级）；微信小程序在同项目 `miniprogram/`。

### 顶层 HTML

| 分组 | 页面 |
|------|------|
| 游戏主站 | `index.html` |
| 仓库 / 背包 | `bag.html` |
| 协议 | `agreement.html` |
| 归档 | `archive/`（含 `history-legacy.html`、旧资源） |

### 子目录

| 路径 | 用途 |
|------|------|
| `css/` | `demo2.css`（主视觉）`base.css` `demo.css` `tool.css` |
| `js/` | `demo2.js` `bag.js` `fisher-api.js` `sfx.js` + `js/min/` 压缩产物 |
| `assets/fish/` | 鱼类 SVG |
| `logs/` | PM2 日志 |

### 关键静态入口

- 样式/逻辑：`css/demo2.css` + `js/demo2.js`（+ `sfx.js`）
- API 封装：`js/fisher-api.js`（本地 API 约 `18041`）
- **无** locales / shell / 主题体系

### 关系

- `p/game/` 下目前 **唯一** `web/`；`p0-1` / `p0-2` 以小程序为主，无平行 `web/`。
- 与主站/行情站无关；身份默认独立（DEC-0009）。

---

## 6. 其他 web 根

| 状态 | 说明 |
|------|------|
| 活跃 | 仅上列 5 个（`web` / `open` / `markets` / `a1` / `fisher`） |
| 已迁出 | `p/a`、`p/yuce`、`p/we` → 仓库外归档（`p/README.md`） |
| 非站点 | `p/game/p0-*` 无 `web/`；`docs/` `ops/` 内 HTML 为草稿/工具，非产品根 |

---

## 7. 对照速查

| 站点 | 域名 | 语言 | 壳层/i18n | 与主站关系 |
|------|------|------|-----------|------------|
| `web/` | www.ai24x.com | 多语 | shell + locales | 真源 Token 站 |
| `p/open/web/` | open.ai24x.com | 多语 | 同构 | 近镜像；API 同源 BYOK |
| `p/markets/web/` | markets.ai24x.com | en | 无 shell/locales | 独立国际行情 |
| `p/a1/web/` | a.ai24x.com | zh | shell（无 i18n） | 独立国内行情 |
| `fisher/web/` | （本地/待上架） | zh | 游戏自有 CSS/JS | 游戏矩阵样版 |

---

## 8. 维护提示

1. 改 **Token 用户可见文案**：优先 `web/config/locales.js`（及 HTML 默认中文）；open 是否同步按产品决定。  
2. 改 **open API 指向**：只动 `p/open/web/js/api.js` 的 open 同源逻辑，勿把 open 指回 core。  
3. 行情两站 **禁止互相覆盖目录**；SEO 增量主要在 `p/markets/web/seo/`。  
4. A1 手机改动看 `p/a1/web/m/`，桌面主路径看 `index.html` / `gd.html`。  
5. 改 `web/*.html` 的 `<head>` 须保证标签闭合、UTF-8（见 `.cursor/rules/static-html-safety.mdc`）。
