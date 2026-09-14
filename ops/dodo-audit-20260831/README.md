# Dodo 临时脚本审计记录（2026-08-31 司令执行）

## 结论
- ✅ **删除**（生产 api/ 目录已清空）：
  - `check_dodo2.py` / `check_dodo_q.py`：一次性 PG 诊断脚本，**硬编码明文数据库密码**，无复用价值 → 删除（未做任何备份，内容已打码审计留档于本目录上方审计输出）
  - `check_dodo_payment.py`：一次性 sqlite 诊断脚本（生产用 PG，无用）→ 删除
  - `dodo_backfill.py` / `dodo_backfill_v2.py`：从 api/ 移至 04 运维区 `C:\Users\Administrator\ops\dodo-tools\`（密钥从 `.env` 读取，无硬编码；已补 `sys.path`/`env_path` 指向 `C:\ai24x01\api`）
- ✅ **保留原位**：`api/data/shared_pool_usage.json`（共享池用量运行时状态，无敏感，今日仍在更新）

## 安全要点
- 所有密钥均未进入 git / 本地仓库 / 群消息；删除的含密码脚本未做副本留存（避免明文扩散）
- 保留的 dodo_backfill 脚本运行时从 `C:\ai24x01\api\.env` 读取 `DODO_API_KEY` / `DATABASE_URL` 等

## 本目录文件
- `dodo_backfill.py` / `dodo_backfill_v2.py`：与 04 `ops\dodo-tools\` 一致的本地副本（改后版）
