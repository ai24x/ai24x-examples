# -*- coding: utf-8 -*-
"""生产入口（open API / Windows NSSM）。默认端口 18080。"""
from __future__ import annotations

import multiprocessing
import os
import sys


def main() -> None:
    multiprocessing.freeze_support()
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    os.chdir(here)

    host = (os.getenv("API_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int((os.getenv("API_PORT") or "18080").strip() or "18080")
    except ValueError:
        port = 18080
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
