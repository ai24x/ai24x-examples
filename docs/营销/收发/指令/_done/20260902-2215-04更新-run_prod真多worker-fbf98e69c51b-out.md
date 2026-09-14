# 04 回执：run_prod 真多 worker

- **时间**：2026-09-02 22:12+
- **代码**：`fbf98e69c51b`（`api/run_prod.py` + open 同款）；验收脚本修复 `30bd9fb`
- **NSSM**：
  - `AI24X-core` / `AI24X-open-api`：`AppParameters=run_prod.py`（不再 `-m uvicorn ... --workers`）
- **验收**（正确统计 `multiprocessing.spawn` 子进程）：
  - core `:8002` → **spawn_workers=4** `WORKERS_OK`
  - open `:18080` → **spawn_workers=4** `WORKERS_OK`
  - `/health` 正常
- **说明**：Windows venv 会再起一层 `Program Files\Python311`，属正常；此前误判「只有 1 worker」是因为只扫命令行含 uvicorn 的进程，漏了 `spawn_main`。

# ✅ 04更新完成｜run_prod真多worker｜EXP=fbf98e69c51b HEAD=3f5237316a09 health=3f5237316a09｜core/open 各4 spawn workers
