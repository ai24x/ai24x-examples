# -*- coding: utf-8 -*-
"""推理出口过滤单测（不打上游）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reasoning_filter import (
    ThinkTagStreamScrubber,
    extract_client_visible_text,
    parse_include_reasoning_from_body,
    scrub_think_tags,
    stream_delta_visible_piece,
)


def test_nonstream_content_with_reasoning_hidden():
    msg = {
        "content": "最终答案",
        "reasoning_content": "The user is asking... English draft",
    }
    assert extract_client_visible_text(msg) == "最终答案"
    assert "English" not in extract_client_visible_text(msg)


def test_nonstream_only_reasoning_hidden():
    msg = {"content": "", "reasoning_content": "secret think"}
    assert extract_client_visible_text(msg) == ""
    assert extract_client_visible_text(msg, include_reasoning=True) == "secret think"


def test_reasoning_and_details_fields():
    msg = {"content": None, "reasoning": "r1"}
    assert extract_client_visible_text(msg) == ""
    msg2 = {"content": "", "reasoning_details": [{"text": "rd"}]}
    assert extract_client_visible_text(msg2) == ""
    assert extract_client_visible_text(msg2, include_reasoning=True) == "rd"


def test_stream_interleaved_ignores_reasoning():
    assert stream_delta_visible_piece({"content": "A"}) == "A"
    assert stream_delta_visible_piece({"reasoning_content": "B"}) is None
    assert stream_delta_visible_piece({"content": None, "reasoning": "C"}) is None
    assert (
        stream_delta_visible_piece(
            {"content": None, "reasoning_content": "D"}, include_reasoning=True
        )
        == "D"
    )


def test_think_tags_scrub():
    raw = "前<think>hidden EN</think>后"
    assert scrub_think_tags(raw) == "前后"
    assert scrub_think_tags("<thinking>x</thinking>") == ""


def test_think_tags_stream_split():
    s = ThinkTagStreamScrubber()
    a = s.feed("你好<thi")
    b = s.feed("nk>SECRET</thi")
    c = s.feed("nk>世界")
    d = s.flush()
    out = "".join([a, b, c, d])
    assert "SECRET" not in out
    assert "你好" in out and "世界" in out


def test_parse_include_reasoning():
    assert parse_include_reasoning_from_body({}) is False
    assert parse_include_reasoning_from_body({"include_reasoning": True}) is True
    assert parse_include_reasoning_from_body({"thinking": {"type": "enabled"}}) is True
    assert parse_include_reasoning_from_body({"thinking": {"type": "disabled"}}) is False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL_PASS")
