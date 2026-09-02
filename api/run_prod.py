# -*- coding: utf-8 -*-
"""生产入口（Windows NSSM）：保证 multiprocessing spawn 正确拉满 workers。

NSSM 示例：
  Application = C:\\ai24x01\\api\\venv\\Scripts\\python.exe
  AppDirectory = C:\\ai24x01\\api
  AppParameters = run_prod.py

环境变量：
  API_WORKERS / UVICORN_WORKERS — worker 数（默认 4）
  API_HOST / API_PORT — 默认 127.0.0.1:8002
"""
from __future__ import annotations

import multiprocessing
import os
import sys


def main() -> None:
    # Windows spawn 要求入口可被子进程安全 re-import
    multiprocessing.freeze_support()

    # 保证从 api/ 目录加载 main:app 与本地包
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    os.chdir(here)

    host = (os.getenv("API_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int((os.getenv("API_PORT") or "8002").strip() or "8002")
    except ValueError:
        port = 8002
    try:
        workers = int(
            (os.getenv("API_WORKERS") or os.getenv("UVICORN_WORKERS") or "4").strip()
            or "4"
        )
    except ValueError:
        workers = 4
    workers = max(1, min(workers, 16))

    import uvicorn

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
