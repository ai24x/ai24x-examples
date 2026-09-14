# 完整备份 · cursor接口调用切换BYOK基本正常版（整仓代码 + 各子项目数据库，可回滚）

- **标签**：完整-cursor接口调用切换BYOK基本正常版
- **时间**：2026-09-08
- **备注**：Cursor 接口调用切换 BYOK 基本正常版
- **范围**：整个 `ai24x01` 仓库代码 + 各子项目 `.env` 指向的 PostgreSQL +（若本机有）Markets 静态站

## 包含什么

| 内容 | 路径 |
|------|------|
| Git 全量 bundle（可 clone/fetch 回滚） | `code/repo.bundle` |
| 当前 HEAD 全仓 zip | `code/repo-HEAD.zip` |
| 工作区镜像（含未提交但排除 .env/备份树） | `code/workdir-mirror/` |
| 各库 `pg_dump -Fc` | `db/<dbname>.dump` |
| `.env` 副本（**勿外传、勿提交 git**） | `secrets/` |
| 04 上 Markets 静态 | `sites/markets.ai24x.com/`（仅存在时） |
| 清单 | `manifest.json` |

## 备份

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "docs\备份\20260908-完整-cursor接口调用切换BYOK基本正常版\scripts\backup_full.ps1"
```

## 回滚（默认干跑，加 `--apply` 才写入）

```powershell
# 只还原数据库
python "docs\备份\20260908-完整-cursor接口调用切换BYOK基本正常版\scripts\rollback_full.py" --db-only --apply

# 还原 HEAD zip 代码覆盖工作区
python "docs\备份\20260908-完整-cursor接口调用切换BYOK基本正常版\scripts\rollback_full.py" --code-only --apply

# 库 + 代码
python "docs\备份\20260908-完整-cursor接口调用切换BYOK基本正常版\scripts\rollback_full.py" --apply

# 另加 .env
python "docs\备份\20260908-完整-cursor接口调用切换BYOK基本正常版\scripts\rollback_full.py" --apply --secrets
```

也可用 git bundle：

```powershell
git clone code\repo.bundle restored-repo
```

回滚后重启：`AI24X-core` / `AI24X-open-api` / `AI24X-markets-api`（按需）。

## 注意

- dump / secrets / code 大文件 **不要 push 进 git**
- 本机预演库 ≠ 04 生产库，回滚勿混用
- a1 国内生产在 **副脑03** 时，需在 03 另做完整备份
