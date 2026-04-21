## AI24X 平台 · 子项目：AI 行情官｜灯塔版（1.01）

目标域名：`a.ai24x.com`

端口约定（推荐）：

- **服务器**：`8001`（通过反向代理绑定到 `a.ai24x.com`）
- **本地开发**：`18001`

### 目录结构（统一）
- `web/`：前端页面（演示/产品页）
- `api/`：后端服务（FastAPI）
- `docs/`：规划与算法说明
- `vendor/`：第三方静态依赖（可本地化图表库）
- `scripts/`：启动脚本
- `artifacts/`：历史打包产物（zip 等）

### 前端
- 入口：`web/index.html`（正式入口，后续在此迭代）
- 基线演示：`web/demo.html`（保留作为基线备份）
- 本地图表库（可选）：
  - 放置：`vendor/lightweight-charts.standalone.production.js`
  - `demo.html` 会**本地优先**加载，失败自动回退 CDN

### 静态依赖本地化（限速 + 可恢复）
仅用于第三方静态库（JS/CSS 等），避免批量抓行情数据触发风控。

```powershell
py "scripts/download_vendor.py"
```

下载源配置：`scripts/vendor_sources.json`  
下载状态缓存：`scripts/.vendor_download_state.json`

### 后端（MVP）
- 目录：`api/server/`
- 启动说明见：`api/server/README.md`

本地启动建议（两端联调）：

- 静态页：运行 `scripts/serve.cmd`（会在 `http://127.0.0.1:18001/demo.html` 打开）
- 后端：在 `api/server/` 启动 `uvicorn`（推荐固定：`http://127.0.0.1:18031`；与前端 `API_BASE` 约定一致）

