# 山海渔 · 微信小程序（联调骨架）

## 导入方式

用 **微信开发者工具** → 导入项目 → 选择本目录 `p/game/fisher/miniprogram`（本目录含 `app.json` / `project.config.json`）。

## 本地 API

默认请求 `http://127.0.0.1:18041`（见 `app.js` 的 `globalData.apiBase`）。请先启动：

- `p/game/fisher/scripts/start_api.cmd`，或  
- `pm2 start ecosystem.local.cjs --only fisher-api-18041`（在仓库根目录）

`project.config.json` 已设 `urlCheck: false`，便于开发期访问 HTTP；**上架前**改为 HTTPS 合法域名并打开域名校验。

## 设备标识

`app.js` 中 `devKey` 对应后端 `POST /v1/auth/dev-login`；多机调试请改成不同字符串，以免共用同一存档。
