# web/ — 静态官网（首版）

与规划 **1.0** 对齐：纯 **HTML / CSS / JS**，无构建步骤；由 `api/main.py` 挂载到站点根路径（与 API 同端口）。

> 建议：生产环境主站（`www.ai24x.com`）优先由反向代理直接托管 `web/` 静态文件，避免把主站可用性绑定到数据库/后端；开发联调仍可沿用 `api/main.py` 挂载方式。

## 文件一览

| 类型 | 路径 |
|------|------|
| 页面 | `index.html` `product.html` `pricing.html` `refer.html` `docs.html` `console.html` `partner.html` `about.html` `login.html` `register.html` `404.html` |
| 全局样式 | `css/base.css` |
| 主题 | `css/themes/theme-blue.css` `theme-dark.css` `theme-cards.css` |
| 文案 | `config/locales.js` |
| 脚本 | `js/app.js` `shell.js` `i18n.js` `api.js` |
| 本地入口 | `start_web.bat`（进入 `api` 启动服务，见仓库根 `README`） |

## 联调入口

- **控制台**：`console.html` — 健康检查、用户信息、chat 测试（依赖后端与 DB）
- 测试步骤汇总：`docs/MVP-测试与联调.md`

若你只想本地预览页面、不启用数据库：

- 在 `api/.env` 设置 `SKIP_DB_INIT=true` 后启动 `python main.py`

## 约定

- 新页面沿用 `data-page` + `AI24X_SHELL.mount` + `data-i18n`
- 远程/CDN 缓存导致看不到最新 JS/CSS：改完静态资源后执行  
  `python web/scripts/bump_asset_version.py <新版本号>`（会改写各页 `link`/`script` 的 `?v=`）
- 不提交密钥；API Key 仅存浏览器本地时需在用户协议中说明风险
