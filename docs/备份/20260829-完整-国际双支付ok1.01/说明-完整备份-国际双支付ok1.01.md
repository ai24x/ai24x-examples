# 完整备份 · 国际双支付 ok1.01（整仓代码 + 各子项目数据库，可回滚）

- **标签**：完整-国际双支付ok1.01
- **时间**：2026-08-29
- **范围**：整个 `ai24x01` 仓库代码 + 各子项目 `.env` 指向的 PostgreSQL +（04）Markets 静态站

## 包含什么

| 内容 | 路径 |
|------|------|
| Git 全量 bundle（可 clone/fetch 回滚） | `code/repo.bundle` |
| 当前 HEAD 全仓 zip | `code/repo-HEAD.zip` |
| 工作区镜像（含未提交但排除 .env/备份树） | `code/workdir-mirror/` |
| 各库 `pg_dump -Fc` | `db/<dbname>.dump` |
| `.env` 副本（**勿外传、勿提交 git**） | `secrets/` |
| 04 上 Markets 静态 | `sites/markets.ai24x.com/`（仅 04 有） |

## 子项目 / 库（自动从各 `.env` 发现）

- core / www：`api/.env` → `DATABASE_URL`
- open：`p/open/api/.env` → `DATABASE_URL`
- a1（若本机有）：`p/a1/api/server/.env` → `AI24X_DATABASE_URL`
- markets / game：有独立库则一并 dump
- **04 生产常见**：`ai24x_core_cn` + `ai24x_open_cn`（a1 国内库在副脑03，不在本包）

## 备份

```powershell
# 本机
powershell -NoProfile -ExecutionPolicy Bypass -File docs\备份\20260829-完整-国际双支付ok1.01\scripts\backup_full.ps1

# 副脑04
powershell -NoProfile -ExecutionPolicy Bypass -File C:\ai24x01\docs\备份\20260829-完整-国际双支付ok1.01\scripts\backup_full.ps1
```

## 回滚（默认干跑，加 `--apply` 才写入）

```powershell
# 只还原数据库
python docs\备份\20260829-完整-国际双支付ok1.01\scripts\rollback_full.py --db-only --apply

# 还原 HEAD zip 代码覆盖工作区
python docs\备份\20260829-完整-国际双支付ok1.01\scripts\rollback_full.py --code-only --apply

# 库 + 代码
python docs\备份\20260829-完整-国际双支付ok1.01\scripts\rollback_full.py --apply

# 另加 .env
python docs\备份\20260829-完整-国际双支付ok1.01\scripts\rollback_full.py --apply --secrets
```

也可用 git bundle：

```powershell
git clone code\repo.bundle restored-repo
# 或在现有仓：git fetch code\repo.bundle <branch>:<branch>
```

回滚后重启：`AI24X-core` / `AI24X-open-api` / `AI24X-markets-api`（按需）。

## 注意

- dump / secrets / code 大文件 **不要 push 进 git**
- 本机预演库 ≠ 04 生产库，回滚勿混用
- a1 国内生产在 **副脑03**，需在 03 另做完整备份
