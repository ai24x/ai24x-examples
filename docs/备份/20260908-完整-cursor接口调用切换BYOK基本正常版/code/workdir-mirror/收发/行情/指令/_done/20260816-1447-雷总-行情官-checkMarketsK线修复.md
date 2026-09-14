# 任务书 · 请行情官检查确认 markets K 线修复（2026-08-16 14:47 雷总指令）

## 背景
雷总 10:52 要求优化 markets 国际版 K 线展示（手机版过密不清晰）。此前你（行情官）交付了方案但未落盘，14:45 雷总反馈"打不开/优化失败"，主脑已按你的方案**直接落盘+部署**完成修复。

## 请行情官立即检查确认（重点：验证而非重新开发）
1. **确认代码已生效**：
   - `p\markets\api\server\app\main.py`：api_kline / api_signals 的 `count: int = Query(250, ge=10, le=1500)`（原 500）
   - `p\markets\web\app.html`：新增 `VISIBLE_MAIN`/`showLastN` 函数 + 3 处 `fitContent()` 已替换（K线用 candles.length / 量能用 data.candles.length / RSI 用 times.length）
2. **实测验证**：`GET /api/kline?symbol=AAPL` 默认应返回 ≤250 根；手机视口（375px）打开 app.html 确认最近 ~120 根清晰、量能/RSI 同区间对齐
3. **若发现可优化点**：补充建议（不要大改，避免再次中断服务；改动需先备份 + 通知主脑部署）
4. **回执**：✅ 确认修复到位 / ⚠️ 发现问题（附截图/根因）+ 建议

## 注意
- 服务已由 nssm 正规托管（AI24X-markets-api，RUNNING，18012）
- 改动需谨慎，若需再改请先备份 + 主脑协同部署
