# p/game/core — 游戏矩阵中台（统一后端）

> 定位：矩阵所有小游戏/工具共用的「账号/积分/广告/埋点/排行/挑战」服务。
> 技术栈：FastAPI + PostgreSQL 15（单库多租户，按 app_id 隔离）+ PM2。与 a1（18011）同栈，经验直接复用。
> 状态：✅ 代码骨架可运行（2026-08-13，本地 18043 全链路验证通过：登录/me/排行榜/埋点）。

## 一、为什么有中台

矩阵 = 一套中台 + 每款独立 AppID。中台负责所有游戏共用能力，游戏只负责玩法：

| 能力 | 说明 | 状态 |
|---|---|---|
| 账号 | wx.login → code2session → openid/unionid → JWT | 设计定稿 |
| 星币/成就 | 跨游戏虚拟资产（不可兑换现金，合规） | 设计定稿 |
| 广告 | 优量汇+穿山甲双聚合封装、激励视频服务端验证、点位后台可配 | 设计定稿 |
| 埋点 | 首局完成率/次留/分享率/人均视频数（对接 5 条验收标准） | 设计定稿 |
| 排行 | 好友/全服/每日榜单（好友榜走微信开放数据域渲染） | 设计定稿 |
| 挑战 | 好友挑战记录（异步 PK 数据源） | 设计定稿 |

## 二、目录结构

- api/   FastAPI 工程（main.py / routers / models / services）
- db/    建库建表 SQL + 迁移脚本
- docs/  架构、schema、接口文档

## 三、核心接口草案（REST，/api/v1）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/login | code 换 token（openid/unionid） |
| GET | /me | 用户信息+星币 |
| GET | /games | 游戏列表（矩阵互通用） |
| GET | /games/{key}/config | 游戏配置（玩法参数/广告点位） |
| POST | /events | 埋点上报（批量） |
| GET | /leaderboard?scope=all|daily|friends | 排行榜 |
| POST | /challenges | 发起好友挑战 |
| GET | /challenges/{id} | 挑战详情/回传比分 |
| POST | /ads/reward-verify | 激励视频服务端验证+发放奖励 |

## 四、多租户

- 所有业务表带 game_id / appid 字段；游戏间数据隔离，账号（unionid）全局唯一。
- 环境：先本地 PG15（与 fisher 同实例），上线后独立库 game_core。
