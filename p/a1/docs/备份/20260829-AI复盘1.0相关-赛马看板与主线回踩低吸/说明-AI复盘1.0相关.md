# AI复盘 1.0 相关代码快照

- 备份时间：2026-08-29
- 用途：上线「栏目赛马周报看板 + 主线回踩低吸(mlpb)」前本地快照，便于回滚对照
- 范围：桌面/手机 AI复盘页、bjscreener 前后端、shell 导航文案、日报顺风承压相关

## 文件清单
- web/gd.html
- web/m/gd.html
- web/js/bjscreener.js (?v=132)
- web/css/bjscreener.css (?v=98)
- web/js/shell.js（菜单：AI复盘）
- api/server/app/bj_screener.py（mlpb_view / 赛马入库）
- api/server/app/main.py（market 白名单）
- api/server/app/daily_report.py（结构顺·当日承压）

## 功能要点
1. 栏目赛马周报看板（#bj-raceboard）
2. 新栏 mlpb「主线回踩低吸」
3. 大盘徽章「结构顺 · 当日承压」横排优化
4. 菜单文案 复盘 → AI复盘
