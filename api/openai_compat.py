# -*- coding: utf-8 -*-
"""OpenAI Chat Completions 兼容层（P0）。

对外：POST /v1/chat/completions（Bearer / X-API-Key）
对内：复用 ChatService.process_chat_request → 路由 / 扣费 / 用量
流式：先走完整非流链路（已计费），再按 SSE 切块下发（兼容 Open WebUI / LobeChat）
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional, Tuple

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from schemas import ChatRequest as ChatRequestSchema, ChatResponse


# 生态常用名 → 平台档位；无匹配默认 flash（需求单）
_OPENAI_MODEL_ALIASES: Dict[str, str] = {
    "gpt-4o-mini": "flash",
    "gpt-4o": "flash",
    "gpt-4-turbo": "pro",
    "gpt-4": "pro",
    "gpt-3.5-turbo": "flash",
    "gpt-3.5-turbo-16k": "flash",
    "gpt-5-mini": "flash",
    "gpt-5": "pro",
    "claude-3-5-sonnet": "pro",
    "claude-3-5-haiku": "flash",
    "claude-3-haiku": "flash",
    "claude-3-opus": "ultra",
    "gemini-pro": "pro",
    "gemini-1.5-flash": "flash",
    "gemini-1.5-pro": "pro",
    "text-davinci-003": "flash",
}


def extract_api_key(request: Request) -> Optional[str]:
    """X-API-Key 或 Authorization: Bearer <key>。"""
    xk = (request.headers.get("X-API-Key") or "").strip()
    if xk:
        return xk
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def map_model_name(requested: Optional[str]) -> str:
    """映射到平台 model；未知名默认 flash。"""
    raw = (requested or "").strip()
    if not raw:
        return "flash"
    low = raw.lower()
    if low in ("free",):
        return "auto"
    # 平台自有档 / VIP 点名
    if low in (
        "auto",
        "flash",
        "pro",
        "ultra",
        "shared",
        "free-shared",
        "free_shared",
    ) or low.startswith("vip-"):
        return low
    try:
        from model_router import MODEL_LAYER

        if low in MODEL_LAYER:
            return low
    except Exception:
        pass
    if low in _OPENAI_MODEL_ALIASES:
        return _OPENAI_MODEL_ALIASES[low]
    return "flash"


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                if p.get("type") == "text" or "text" in p:
                    parts.append(str(p.get("text") or ""))
                elif p.get("type") == "image_url":
                    parts.append("[image]")
        return "\n".join(x for x in parts if x)
    return str(content)


def messages_to_prompt(messages: Any) -> str:
    """OpenAI messages[] → 现有 prompt 字符串（tool/function 降级忽略）。"""
    if not isinstance(messages, list) or not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="messages 不能为空",
        )
    blocks: List[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        if role in ("tool", "function"):
            # P0：不实现 function calling，忽略工具消息
            continue
        text = _content_to_text(m.get("content")).strip()
        if not text:
            continue
        if role == "system":
            blocks.append(f"[system]\n{text}")
        elif role == "assistant":
            blocks.append(f"[assistant]\n{text}")
        else:
            # user / 未知角色按 user
            blocks.append(f"[user]\n{text}")
    prompt = "\n\n".join(blocks).strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="messages 中无有效文本内容",
        )
    if len(prompt) > 10000:
        prompt = prompt[:10000]
    return prompt


def openai_error_body(
    message: str,
    *,
    err_type: str = "invalid_request_error",
    code: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "error": {
            "message": message,
            "type": err_type,
            "code": code,
            "param": None,
        }
    }


def map_http_exception_to_openai(exc: HTTPException) -> Tuple[int, Dict[str, Any]]:
    code = int(exc.status_code)
    msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    if code == 401:
        return code, openai_error_body(
            msg or "Invalid API key",
            err_type="invalid_request_error",
            code="invalid_api_key",
        )
    if code == 402:
        return code, openai_error_body(
            msg or "Insufficient quota",
            err_type="insufficient_quota",
            code="insufficient_quota",
        )
    if code == 403:
        return code, openai_error_body(
            msg or "Forbidden",
            err_type="invalid_request_error",
            code="permission_denied",
        )
    if code == 429:
        return code, openai_error_body(
            msg or "Rate limit exceeded",
            err_type="rate_limit_error",
            code="rate_limit_exceeded",
        )
    if code >= 500:
        return code, openai_error_body(
            msg or "Server error",
            err_type="server_error",
            code="server_error",
        )
    return code, openai_error_body(msg or "Bad request", err_type="invalid_request_error", code="bad_request")


def openai_error_response(exc: HTTPException) -> JSONResponse:
    status_code, body = map_http_exception_to_openai(exc)
    return JSONResponse(status_code=status_code, content=body)


def build_chat_request_schema(body: Dict[str, Any]) -> ChatRequestSchema:
    model = map_model_name(body.get("model"))
    prompt = messages_to_prompt(body.get("messages"))
    try:
        temperature = float(body.get("temperature") if body.get("temperature") is not None else 0.7)
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(2.0, temperature))
    try:
        max_tokens = int(body.get("max_tokens") if body.get("max_tokens") is not None else 1000)
    except (TypeError, ValueError):
        max_tokens = 1000
    max_tokens = max(1, min(4000, max_tokens))
    return ChatRequestSchema(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=bool(body.get("stream")),
    )


def completion_id() -> str:
    return "chatcmpl-" + uuid.uuid4().hex[:24]


def to_openai_completion(resp: ChatResponse, *, requested_model: str, cmpl_id: str) -> Dict[str, Any]:
    total = max(0, int(resp.token_count or 0))
    # 无细粒度拆分时按约 30/70 估 prompt/completion（仅展示；扣费仍用 total）
    prompt_tokens = max(1, int(total * 0.3)) if total else 0
    completion_tokens = max(0, total - prompt_tokens) if total else 0
    model_out = resp.model or requested_model or "flash"
    return {
        "id": cmpl_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_out,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": resp.response or ""},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        },
    }


def _chunk_text(text: str, size: int = 24) -> List[str]:
    s = text or ""
    if not s:
        return [""]
    return [s[i : i + size] for i in range(0, len(s), size)]


def iter_sse_from_completion(resp: ChatResponse, *, requested_model: str, cmpl_id: str) -> Iterator[str]:
    """将已完成的回复切成 OpenAI SSE chunk（计费已在上游完成）。"""
    model_out = resp.model or requested_model or "flash"
    created = int(time.time())

    def pack(payload: Dict[str, Any]) -> str:
        return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

    # role 首包
    yield pack(
        {
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_out,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ],
        }
    )
    for piece in _chunk_text(resp.response or "", 32):
        if not piece:
            continue
        yield pack(
            {
                "id": cmpl_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_out,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": piece},
                        "finish_reason": None,
                    }
                ],
            }
        )
    yield pack(
        {
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_out,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
    )
    yield "data: [DONE]\n\n"


def streaming_response(resp: ChatResponse, *, requested_model: str, cmpl_id: str) -> StreamingResponse:
    return StreamingResponse(
        iter_sse_from_completion(resp, requested_model=requested_model, cmpl_id=cmpl_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
