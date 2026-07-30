#!/usr/bin/env python3
"""OpenRouter / 路由烟测（本机）。

用法（在 api/ 目录或仓库根）：
  python api/scripts_openrouter_smoke.py

不调真实 HTTP 上游时：仅打印 resolve_chain + upstream 配置是否含 Key。
设 OPENROUTER_SMOKE_LIVE=1 且已配置 OPENROUTER_API_KEY 时，会打一条真实 chat。
"""
from __future__ import annotations

import os
import sys

# 保证可 import api 包内模块
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main() -> int:
    from model_router import (
        _layer_upstream,
        _openrouter_model_for_layer,
        _upstream_mode,
        list_models_public,
        resolve_chain,
        run_routed_chat,
    )

    mode = _upstream_mode()
    print("TOKEN_LLM_UPSTREAM mode =", mode)
    for ly in ("L0", "L1", "L2", "L3", "QI"):
        up = _layer_upstream(ly)
        print(
            f"  {ly}: provider={up.get('provider')} model={up.get('model')} "
            f"key={'yes' if up.get('key') else 'NO'} "
            f"default_or={_openrouter_model_for_layer(ly)}"
        )
    print("FREE chain:", resolve_chain(requested_model="auto", is_vip=False))
    print("VIP  chain:", resolve_chain(requested_model="auto", is_vip=True))
    pub = list_models_public(is_vip=False)
    print(
        "public:",
        pub.get("upstream_mode"),
        "ready=",
        (pub.get("upstream") or {}).get("direct_ready")
        or (pub.get("upstream") or {}).get("openrouter_ready"),
    )

    if (os.getenv("OPENROUTER_SMOKE_LIVE") or "").strip() not in ("1", "true", "TRUE"):
        print("Skip live call (set OPENROUTER_SMOKE_LIVE=1 to hit OpenRouter).")
        return 0

    if not _layer_upstream("L1").get("key"):
        print("ERROR: no OPENROUTER_API_KEY (or TOKEN_LLM_KEY)")
        return 2

    r = run_routed_chat(
        prompt="Reply with exactly: OK",
        requested_model="flash",
        is_vip=False,
        max_tokens=32,
    )
    print("live ok=", r.ok, "provider=", r.provider, "model=", r.model, "layer=", r.layer)
    print("text=", (r.text or "")[:200])
    print("attempts=", r.attempts)
    return 0 if r.ok and r.provider != "stub" else 1


if __name__ == "__main__":
    raise SystemExit(main())
