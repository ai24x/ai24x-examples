## 目标
把 AI 行情官“信号/markers/逐根提示”的计算从前端迁到服务端：

- 前端只负责：请求数据 + 渲染 K 线 + 渲染 markers + 展示中性提示文案
- 服务端负责：根据 K 线数据生成 markers（以及可选的 tooltip 文案）

核心收益：
- 降低被抄袭：浏览器端不再下发核心算法
- 合规可控：输出口径集中在服务端，可统一开关/灰度

---

## 现状（a1）
- `web/demo.html`：包含完整信号算法（浏览器可见、可复制）
- `api/server/`：暂无同等信号算法实现（需新增）

---

## a2 约定（本目录）
- 静态：`http://127.0.0.1:18001/`
- API：`http://127.0.0.1:18011/`
- SW 缓存名：`ai24x-a1-static-v1`（避免与旧缓存混用）

---

## MVP 版本（建议先做：1–2 天）
### 1) 新增 API：signals（服务端输出 markers）
- 路由建议：`GET /api/a2/signals?secid=...&period=day|week|month`
- 输出建议：
  - `markers`: lightweight-charts `SeriesMarker` 兼容结构（或后端自定义结构，前端再映射）
  - `version`: 算法版本号（便于灰度与回溯）
  - `meta`: 可选（参数摘要、数据源等；对外可不返回）

### 2) 前端 demo 改造（只渲染，不计算）
- 仍由前端拉取 K 线（或由后端统一返回）
- markers 改为：调用 `/api/a2/signals` 后 `series.setMarkers(markers)`
- 前端删除/隔离 `buildLeishenMarkersAndLabels`（至少不在对外页面交付）

### 3) 回归对比（必做但可轻量）
- 固定一组 `secid+period`，比对：
  - markers 数量/时间戳是否稳定
  - 前端展示是否正常（不崩、不闪、不遮挡）

---

## 对齐版本（3–7 天，按一致性要求）
如果需要与当前前端算法输出高度一致：
- 服务端完整复刻边界处理与参数
- 增加对比测试：同一份 candles 输入，输出 markers 应一致（或差异可解释）
- tooltip 文案建议也服务端化（否则仍需前端“解释逻辑”）

---

## 长期工程化（1–3 周）
- 版本化：`signals_version`
- 灰度：按用户/套餐/地区开关
- 风控：限流、缓存、审计日志
- 降级：服务端失败时只展示均线与行情（不展示 markers）

