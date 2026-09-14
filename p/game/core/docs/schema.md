# 中台数据库 Schema 草案（PostgreSQL 15）

> 库名：game_core（本地先建 game_core 测试库，或与 a1 预发库并存，见 db/ 说明）

## users（账号，unionid 全局唯一）

| 列 | 类型 | 说明 |
|---|---|---|
| id | bigserial PK | |
| appid | text | 注册来源 appid |
| openid | text | 微信 openid（appid 内唯一） |
| unionid | text | 同主体全局 id（唯一索引） |
| nickname | text | |
| avatar | text | |
| stars | int default 0 | 星币（不可兑换现金） |
| level | int default 1 | 段位/等级 |
| created_at | timestamptz | |
| last_seen_at | timestamptz | |

## games（游戏注册）

| 列 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| key | text unique | 如 p01-bietingta |
| name | text | |
| wx_appid | text | |
| status | text | draft/review/live/paused |
| platform | text | wechat/douyin/h5 |

## game_configs（玩法/运营配置，JSON 可热更新）

- game_id, cfg_key（ad_slots/levels/shares...）, cfg_json, updated_at

## ad_rewards（激励视频发放台账，防刷）

- id, game_id, user_id, slot_key, reward_type, reward_value, verify_token, status(pending/paid/void), ts

## leaderboards（榜单）

- id, game_id, scope(all/daily/friends), period(YYYY-MM-DD), seed, user_id, score, payload(json), rank, ts
- 索引：(game_id, scope, period, seed) + score desc

## challenges（好友挑战）

- id, game_id, seed, from_user, to_user, from_score, to_score, status(sent/accepted/done/expired), ts
- 异步 PK：双方各自玩同一种子，服务端比成绩。

## events（埋点，可分区/归档）

- id, appid, user_id, event(first_done/retain/share/ad_watch/...), params(json), ts

## stars_transactions（星币流水，合规留痕）

- id, user_id, delta, reason(ad_reward/daily_bonus/consume), ref, ts
