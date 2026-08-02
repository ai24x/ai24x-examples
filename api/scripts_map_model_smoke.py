# -*- coding: utf-8 -*-
"""本地烟测 map_model_name：品牌档 / shared / VIP 短别名 / OpenAI drop-in。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai_compat import map_model_name

CASES = [
    ("flash", "flash"),
    ("pro", "pro"),
    ("ultra", "ultra"),
    ("auto", "auto"),
    ("shared", "shared"),
    ("free-shared", "shared"),
    ("vip-kimi", "vip-kimi"),
    ("kimi", "vip-kimi"),
    ("mimo", "vip-mimo"),
    ("qwen", "vip-qwen-max"),
    ("gpt", "vip-gpt5"),
    ("claude", "vip-claude-sonnet"),
    ("gemini", "vip-gemini-pro"),
    ("vip-claude-sonnet", "vip-claude-sonnet"),
    # OpenAI drop-in 仍落品牌档（不是真名模）
    ("gpt-4o", "flash"),
    ("gpt-5", "pro"),
    ("claude-3-5-sonnet", "pro"),
    # 遗留层名保持
    ("deepseek-flash", "deepseek-flash"),
]


def main() -> int:
    bad = 0
    for raw, want in CASES:
        got = map_model_name(raw)
        ok = got == want
        print(("PASS" if ok else "FAIL"), raw, "→", got, "(want", want + ")")
        if not ok:
            bad += 1
    print("RESULT", "OK" if bad == 0 else f"{bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
