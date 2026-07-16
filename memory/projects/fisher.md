# 山海渔 Fisher

> 更新：2026-07-16｜目录：`p/fisher/`｜身份默认独立（DEC-0009）

## 定位

- 垂钓 → 卖鱼 → 升级闭环；合规口径偏「垂钓社区 / 渔获工具」
- 微信小程序优先；H5 已较完整

## 入口

| 环境 | 前端 | API |
|------|------|-----|
| 本地 | `http://127.0.0.1:18002/` | `18041`（需本机 PostgreSQL） |
| 生产 | 未挂 PM2/Nginx | 预留 8003（见 PORTS） |

页面：`index.html`（demo2）、`bag.html`、`agreement.html`；旧版在 `web/archive/`

## 现状

- API：health、dev-login、me、game（fish/sell/spot/rod/shop）、catalog、fishery、market
- 小程序：`miniprogram/` 联调骨架
- 技术债：Alembic、pytest、装备耐久自动扣减等（见 `docs/产品优化路线图-v2.1.md`）

## 近期修复（2026-05）

- `showToast` 暴露到全局；弹窗 z-index 栈修复；钓场入口；漂流瓶生成条件

## 下一步（建议）

1. 本地 PG + `fisher-api-18041` 跑通闭环
2. 生产上线方案另排（勿与 A1 抢带宽）
3. 合规上架路径（避开网游/虚拟币提现表述）
