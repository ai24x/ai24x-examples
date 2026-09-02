# -*- coding: utf-8 -*-
"""上游并发闸门：限制同时打出去的 LLM HTTP，避免线程池/连接池被长阻塞打满。

env:
  TOKEN_LLM_MAX_INFLIGHT     最大同时上游调用数（默认 24）
  TOKEN_LLM_INFLIGHT_WAIT_S  等槽位秒数，超时抛 UpstreamBusyError（默认 3）
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional


class UpstreamBusyError(RuntimeError):
    """In-flight upstream slots exhausted."""


_sem: Optional[threading.BoundedSemaphore] = None
_sem_n = 0
_lock = threading.Lock()


def _max_inflight() -> int:
    try:
        return max(1, int((os.getenv("TOKEN_LLM_MAX_INFLIGHT") or "24").strip() or "24"))
    except ValueError:
        return 24


def _wait_s() -> float:
    try:
        return max(0.1, float((os.getenv("TOKEN_LLM_INFLIGHT_WAIT_S") or "3").strip() or "3"))
    except ValueError:
        return 3.0


def _get_sem() -> threading.BoundedSemaphore:
    global _sem, _sem_n
    n = _max_inflight()
    with _lock:
        if _sem is None or _sem_n != n:
            _sem = threading.BoundedSemaphore(n)
            _sem_n = n
        return _sem


@contextmanager
def upstream_slot() -> Iterator[None]:
    sem = _get_sem()
    if not sem.acquire(timeout=_wait_s()):
        raise UpstreamBusyError("upstream_busy")
    try:
        yield
    finally:
        sem.release()


def try_acquire_upstream_slot() -> bool:
    """流式路径用：成功返回 True；失败不占槽。"""
    return bool(_get_sem().acquire(timeout=_wait_s()))


def release_upstream_slot() -> None:
    try:
        _get_sem().release()
    except ValueError:
        # BoundedSemaphore 超额 release
        pass
