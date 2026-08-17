#!/usr/bin/env python3
"""
运维预警 CLI：定时巡检 + 飞书推送（复用 ops_alert 逻辑）。

用法（api/ 目录）：
  python scripts_ops_alert.py            # 巡检 + 推送
  python scripts_ops_alert.py --dry-run  # 只打印，不推送
  python scripts_ops_alert.py --reset    # 清空去抖状态

注册 Windows 计划任务（每 15 分钟）：
  powershell -ExecutionPolicy Bypass -File scripts/register_ops_alert_cron.ps1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import SessionLocal  # noqa: E402
from ops_alert import reset_state, run_check  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if a.startswith("--")]
    if "--reset" in args:
        reset_state()
        print("[ops_alert] 去抖状态已清空")
        return 0

    dry = "--dry-run" in args
    db = SessionLocal()
    try:
        result = run_check(db, push=not dry, dry_run=dry)
    finally:
        db.close()

    if dry:
        print("--- dry-run（未推送、未改状态） ---")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if result.get("pushed"):
        print("[ops_alert] 已推送飞书")
    elif result.get("skipped") == "disabled":
        print("[ops_alert] 预警总开关已关闭（可在管理台开启）")
    elif not dry:
        print("[ops_alert] 未推送（webhook 未配置或冷却中）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())