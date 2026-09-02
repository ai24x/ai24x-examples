# -*- coding: utf-8 -*-
"""网关出口：推理内容强制过滤（与「是否向上游关闭 thinking」分离）。

默认：客户端只见最终正文；reasoning_* / think 标签一律丢弃。
仅当请求显式 include_reasoning / show_thinking 时才允许把推理并入可见文本。
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

# 常见思考标签（不含属性的简单开闭；流式用状态机处理拆片）
_THINK_TAG_NAMES = ("think", "thinking", "reasoning", "redacted_reasoning")
_THINK_OPEN_RE = re.compile(
    r"<\s*(?:think|thinking|reasoning|redacted_reasoning)\b[^>]*>",
    re.IGNORECASE,
)
_THINK_CLOSE_RE = re.compile(
    r"</\s*(?:think|thinking|reasoning|redacted_reasoning)\s*>",
    re.IGNORECASE,
)
_THINK_BLOCK_RE = re.compile(
    r"<\s*(?:think|thinking|reasoning|redacted_reasoning)\b[^>]*>.*?"
    r"</\s*(?:think|thinking|reasoning|redacted_reasoning)\s*>",
    re.IGNORECASE | re.DOTALL,
)


def env_allows_upstream_thinking() -> bool:
    """是否允许向上游开启思考（运维 env）；与客户端是否可见无关。"""
    for key in ("UPSTREAM_THINKING", "DEEPSEEK_THINKING"):
        if (os.environ.get(key) or "0").strip() in ("1", "true", "TRUE", "yes"):
            return True
    return False


def parse_include_reasoning_from_body(body: Optional[dict[str, Any]]) -> bool:
    """请求级显式开启才返回 True；缺省 False。"""
    if not isinstance(body, dict):
        return False
    for key in ("include_reasoning", "show_thinking", "show_reasoning"):
        if key not in body:
            continue
        v = body.get(key)
        if v is True:
            return True
        if v is False:
            return False
        s = str(v or "").strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
    thinking = body.get("thinking")
    if isinstance(thinking, dict):
        t = str(thinking.get("type") or "").strip().lower()
        if t in ("enabled", "enable", "on"):
            return True
        if t in ("disabled", "disable", "off"):
            return False
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict):
        effort = str(reasoning.get("effort") or "").strip().lower()
        if effort and effort not in ("none", "off", "disabled", "0"):
            return True
    return False


def client_may_see_reasoning(*, include_reasoning: bool = False) -> bool:
    """客户端可见推理：仅请求显式开启（不再用全局 env 放开出口）。"""
    return bool(include_reasoning)


def scrub_think_tags(text: str) -> str:
    """去掉完整 <think>/<thinking>/<reasoning> 块；残留开闭标签一并剥掉。"""
    if not text:
        return ""
    out = _THINK_BLOCK_RE.sub("", text)
    out = _THINK_OPEN_RE.sub("", out)
    out = _THINK_CLOSE_RE.sub("", out)
    return out.strip()


def _reasoning_field_text(msg: dict[str, Any]) -> str:
    for key in ("reasoning_content", "reasoning"):
        v = msg.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    rds = msg.get("reasoning_details")
    if isinstance(rds, list) and rds:
        parts: list[str] = []
        for item in rds:
            if isinstance(item, dict):
                t = item.get("text") or item.get("content") or ""
                if t:
                    parts.append(str(t))
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        if parts:
            return "\n".join(parts).strip()
    return ""


def extract_client_visible_text(
    msg: Optional[dict[str, Any]],
    *,
    include_reasoning: bool = False,
) -> str:
    """从上游 message 抽出客户端可见正文；默认永不回退到推理字段。"""
    msg = msg if isinstance(msg, dict) else {}
    content = msg.get("content")
    if content is None:
        text = ""
    elif isinstance(content, str):
        text = content
    elif isinstance(content, list):
        # multipart：只拼 text 类
        bits: list[str] = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict):
                t = part.get("text") or part.get("content")
                if t:
                    bits.append(str(t))
        text = "".join(bits)
    else:
        text = str(content)

    show = client_may_see_reasoning(include_reasoning=include_reasoning)
    if show:
        if not str(text).strip():
            text = _reasoning_field_text(msg)
        return str(text or "").strip()

    # 默认：丢弃一切推理字段，并清洗正文里的 think 标签
    return scrub_think_tags(str(text or ""))


def stream_delta_visible_piece(
    delta: Optional[dict[str, Any]],
    *,
    include_reasoning: bool = False,
) -> Optional[str]:
    """流式：默认只取 delta.content；开启显示时才允许 reasoning_*。"""
    if not isinstance(delta, dict):
        return None
    piece = delta.get("content")
    if client_may_see_reasoning(include_reasoning=include_reasoning):
        if piece is None:
            piece = delta.get("reasoning_content")
        if piece is None:
            piece = delta.get("reasoning")
        if piece is None:
            return None
        return str(piece)
    # 默认：忽略一切推理字段
    if piece is None:
        return None
    return str(piece)


class ThinkTagStreamScrubber:
    """跨 SSE 分片剥离 think 类标签；开启 include_reasoning 时透传原文。"""

    __slots__ = ("_include", "_buf", "_in_think")

    def __init__(self, *, include_reasoning: bool = False) -> None:
        self._include = bool(include_reasoning)
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        if self._include:
            return chunk
        if not chunk:
            return ""
        self._buf += chunk
        out: list[str] = []
        while self._buf:
            if self._in_think:
                m = _THINK_CLOSE_RE.search(self._buf)
                if not m:
                    # 可能截在 </thi…；保留尾部以防漏关标签
                    keep = min(32, len(self._buf))
                    self._buf = self._buf[-keep:] if len(self._buf) > keep else self._buf
                    # 若缓冲过大仍无闭合，整段丢弃防泄露
                    if len(self._buf) > 64 and "<" not in self._buf:
                        self._buf = ""
                    break
                self._buf = self._buf[m.end() :]
                self._in_think = False
                continue
            m = _THINK_OPEN_RE.search(self._buf)
            if not m:
                # 可能截在 <thi…；保留末尾短前缀
                lt = self._buf.rfind("<")
                if lt >= 0 and len(self._buf) - lt < 48:
                    out.append(self._buf[:lt])
                    self._buf = self._buf[lt:]
                else:
                    out.append(self._buf)
                    self._buf = ""
                break
            out.append(self._buf[: m.start()])
            self._buf = self._buf[m.end() :]
            self._in_think = True
        return "".join(out)

    def flush(self) -> str:
        if self._include:
            return ""
        if self._in_think:
            self._buf = ""
            self._in_think = False
            return ""
        # 残留未完成的 '<' 前缀直接丢弃，避免半截标签泄露
        if self._buf.startswith("<"):
            self._buf = ""
            return ""
        out = self._buf
        self._buf = ""
        return out


def strip_reasoning_fields_from_messages(messages: Any) -> None:
    """关思考展示时，去掉历史里的推理字段，降低多轮传播。"""
    if not isinstance(messages, list):
        return
    for item in messages:
        if not isinstance(item, dict):
            continue
        item.pop("reasoning_content", None)
        item.pop("reasoning", None)
        item.pop("reasoning_details", None)
