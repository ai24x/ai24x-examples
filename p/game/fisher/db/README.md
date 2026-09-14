# 山海渔·渔悦 · 数据库说明（矩阵样版 1）

> 更新时间：2026-08-12（随 p/fisher → p/game/fisher 迁移整理）

## 现状（运行库）

- 后端：FastAPI + SQLAlchemy + **PostgreSQL**（连接串见 `../api/server/.env` 的 `FISHER_DATABASE_URL`）。
- 当前运行库为 **`ai24x_a_pre`**（与 AI行情官 a1 预发共用本机 PG 实例、共用 `ai24x_a` 账号）。这是历史沿革：本地无 postgres 超级账号口令，暂无法拆分独立库。
- 渔悦在 `ai24x_a_pre` 中共 **16 张 `fisher_*` 表**（spots/species/players/fisheries/workers/assets/orders/clubs/diaries/real_catches/bottles/catch_gallery/audit_log/angler_profiles/asset_showcase/club_members），其中 8 钓场、50 鱼种、36 玩家等为现有数据。
- ⚠️ 共享库风险：a1 与渔悦同库，日常联调互不影响；但**禁止**在渔悦功能里 DROP/TRUNCATE 非 `fisher_*` 前缀的表；生产上线前必须拆分独立库。

## 样本快照（本目录）

| 文件 | 说明 |
|---|---|
| `fisher_dump_20260812.dump` | 16 张 `fisher_*` 表 自定义格式（pg_restore）全量导出 |
| `fisher_dump_20260812.sql` | 同内容纯 SQL（--no-owner --no-privileges，便于阅读/审计） |

快照导出命令（可复现）：

```powershell
$env:PGPASSWORD='Ai24x@2026'
& 'C:\Program Files\PostgreSQL\15\bin\pg_dump.exe' -U ai24x_a -h 127.0.0.1 -p 5432 -d ai24x_a_pre -t 'fisher_*' -Fc -f .\fisher_dump_20260812.dump
```

## 拆分独立库（推荐，需 postgres 超级账号）

拿到超级口令后，执行 `../scripts/init_fisher_db.ps1`（建用户 fisher / 建库 fisher / 恢复快照），并把 `api/server/.env` 改为：

```
FISHER_DATABASE_URL=postgresql+psycopg2://fisher:fisher@127.0.0.1:5432/fisher
```

即完成「代码+数据库」全套独立，后续新玩法子项目（game2/game3…）沿用同样模式：一项目一库一用户。

## 首次启动（空库）

后端启动时 `create_all` 自动建表；种子数据见 `api/server/app/seed_data.py`（启动逻辑内自动灌入）。
