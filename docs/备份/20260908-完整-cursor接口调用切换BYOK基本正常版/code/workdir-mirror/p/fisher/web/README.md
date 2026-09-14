# 山海渔 · 网页（本地）

本目录 **`index.html` 为「海王 · 山海渔」H5 主站**（样式 `css/demo2.css`，逻辑 `js/demo2.js` / `js/sfx.js`；仓库页 `bag.html` + `js/bag.js`）。旧版 API 联调单页在 **`archive/history-legacy.html`**（历史封存）。

## 启动

两种方式任选其一：

- 脚本：`p/fisher/scripts/serve_web.cmd`
- PM2（仓库根）：`pm2 start ecosystem.local.config.js --only fisher-web-18002`

访问主站：`http://127.0.0.1:18002/index.html`  
仓库：`http://127.0.0.1:18002/bag.html`  
封存旧版：`http://127.0.0.1:18002/archive/history-legacy.html`

静态资源：更新后用 **Ctrl+F5** 强制刷新即可。

## 前置条件

后端需要已启动：

- `pm2 start ecosystem.local.config.js --only fisher-api-18041`

或直接运行：`p/fisher/scripts/start_api.cmd`

API 文档：`http://127.0.0.1:18041/docs`
