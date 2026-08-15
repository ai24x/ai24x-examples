"""Load the a1 signal engine by file path — share, don't copy.

加载 p\\a1\\api\\server\\app\\signals.py / scoring.py 为独立虚拟包 a1_engine，
避免与 markets 自己的 app 包同名冲突；相对导入（from .signals import ...）可正常解析。
"""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

_PKG = "a1_engine"


def _find_a1_app_dir() -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(8):
        cand = cur / "p" / "a1" / "api" / "server" / "app"
        if (cand / "signals.py").exists():
            return cand
        cur = cur.parent
    raise RuntimeError("a1 app dir not found")


_A1_APP_DIR = _find_a1_app_dir()

if _PKG not in sys.modules:
    _pkg = types.ModuleType(_PKG)
    _pkg.__path__ = [str(_A1_APP_DIR)]
    sys.modules[_PKG] = _pkg

signals = importlib.import_module(f"{_PKG}.signals")
scoring = importlib.import_module(f"{_PKG}.scoring")
