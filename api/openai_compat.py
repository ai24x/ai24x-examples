# -*- coding: utf-8 -*-
"""OpenAI Chat Completions / Responses 兼容层。

对外：POST /v1/chat/completions、POST /v1/responses（Bearer / X-API-Key）
对内：复用 ChatService → 路由 / 扣费 / 用量
流式：默认真流式透传上游 SSE（TOKEN_LLM_TRUE_STREAM=0 时回退假流式切片）
Completions：支持 tools / tool_calls / role=tool（OpenClaw）；Responses 仍为文本最小兼容。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional, Tuple

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from schemas import ChatRequest as ChatRequestSchema, ChatResponse


def _prompt_max_chars() -> int:
    try:
        return max(2000, int(os.getenv("TOKEN_PROMPT_MAX_CHARS") or "120000"))
    except ValueError:
        return 120000


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


def _normalize_tool_calls(raw: Any) -> Optional[List[Dict[str, Any]]]:
    """规范化 assistant.tool_calls 列表；无效则 None。"""
    if not isinstance(raw, list) or not raw:
        return None
    out: List[Dict[str, Any]] = []
    for tc in raw:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        name = str(fn.get("name") or "").strip()
        if not name and not tc.get("id"):
            continue
        args = fn.get("arguments")
        if args is None:
            args = ""
        elif not isinstance(args, str):
            try:
                args = json.dumps(args, ensure_ascii=False)
            except Exception:
                args = str(args)
        item: Dict[str, Any] = {
            "id": str(tc.get("id") or ("call_" + uuid.uuid4().hex[:24])),
            "type": str(tc.get("type") or "function"),
            "function": {"name": name or "tool", "arguments": args},
        }
        out.append(item)
    return out or None


def extract_tools_payload(body: Dict[str, Any]) -> Tuple[Optional[List[Dict[str, Any]]], Any]:
    """从 Completions body 取出 tools / tool_choice（校验最小形状）。"""
    tools_raw = body.get("tools")
    tool_choice = body.get("tool_choice")
    if tools_raw is None:
        return None, tool_choice
    if not isinstance(tools_raw, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tools 必须是数组",
        )
    tools: List[Dict[str, Any]] = []
    for t in tools_raw:
        if not isinstance(t, dict):
            continue
        # 原样保留 OpenAI function tool 形状
        tools.append(t)
    if not tools:
        return None, tool_choice
    if len(tools) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tools 数量过多，请精简后再试",
        )
    return tools, tool_choice


def messages_to_prompt(messages: Any) -> str:
    """OpenAI messages[] → 现有 prompt 字符串（含 tool 轮，供账本/回退）。"""
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
        text = _content_to_text(m.get("content")).strip()
        if role in ("tool", "function"):
            tid = str(m.get("tool_call_id") or m.get("name") or "").strip()
            label = f"[tool {tid}]" if tid else "[tool]"
            if text:
                blocks.append(f"{label}\n{text}")
            continue
        if role == "assistant":
            tcs = m.get("tool_calls")
            if tcs:
                try:
                    tc_s = json.dumps(tcs, ensure_ascii=False)[:4000]
                except Exception:
                    tc_s = str(tcs)[:4000]
                body = (text + "\n" if text else "") + f"[tool_calls]\n{tc_s}"
                blocks.append(f"[assistant]\n{body}")
                continue
            if text:
                blocks.append(f"[assistant]\n{text}")
            continue
        if not text:
            continue
        if role == "system":
            blocks.append(f"[system]\n{text}")
        else:
            blocks.append(f"[user]\n{text}")
    prompt = "\n\n".join(blocks).strip()
    if not prompt:
        # 仅有空壳 tool 轮时给占位，避免 ChatRequest.prompt 校验失败
        prompt = "Continue."
    lim = _prompt_max_chars()
    if len(prompt) > lim:
        prompt = prompt[:lim]
    return prompt


def normalize_messages_for_upstream(messages: Any) -> Optional[List[Dict[str, Any]]]:
    """清洗 messages 供上游透传（含 tool / assistant.tool_calls）。"""
    if not isinstance(messages, list) or not messages:
        return None
    out: List[Dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        if role in ("tool", "function"):
            item: Dict[str, Any] = {
                "role": role,
                "content": _content_to_text(m.get("content")),
            }
            if m.get("tool_call_id") is not None:
                item["tool_call_id"] = str(m.get("tool_call_id"))
            if m.get("name"):
                item["name"] = str(m.get("name"))
            out.append(item)
            continue
        text = _content_to_text(m.get("content")).strip()
        tcs = _normalize_tool_calls(m.get("tool_calls")) if role == "assistant" else None
        if role == "assistant" and tcs:
            item = {
                "role": "assistant",
                "content": text if text else None,
                "tool_calls": tcs,
            }
            out.append(item)
            continue
        if not text:
            continue
        if role not in ("system", "user", "assistant"):
            role = "user"
        out.append({"role": role, "content": text})
    return out or None


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
    from user_i18n import openai_user_message

    code = int(exc.status_code)
    msg = openai_user_message(exc.detail)
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
    raw_messages = body.get("messages")
    prompt = messages_to_prompt(raw_messages)
    msgs = normalize_messages_for_upstream(raw_messages)
    tools, tool_choice = extract_tools_payload(body)
    try:
        temperature = float(body.get("temperature") if body.get("temperature") is not None else 0.7)
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(2.0, temperature))
    try:
        max_tokens = int(body.get("max_tokens") if body.get("max_tokens") is not None else 1000)
    except (TypeError, ValueError):
        max_tokens = 1000
    max_tokens = max(1, min(16384, max_tokens))
    return ChatRequestSchema(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=bool(body.get("stream")),
        messages=msgs,
        tools=tools,
        tool_choice=tool_choice,
    )


def completion_id() -> str:
    return "chatcmpl-" + uuid.uuid4().hex[:24]


def to_openai_completion(resp: ChatResponse, *, requested_model: str, cmpl_id: str) -> Dict[str, Any]:
    total = max(0, int(resp.token_count or 0))
    # 无细粒度拆分时按约 30/70 估 prompt/completion（仅展示；扣费仍用 total）
    prompt_tokens = max(1, int(total * 0.3)) if total else 0
    completion_tokens = max(0, total - prompt_tokens) if total else 0
    model_out = resp.model or requested_model or "flash"
    tool_calls = getattr(resp, "tool_calls", None)
    content = resp.response or ""
    message: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
        if not str(content).strip():
            message["content"] = None
    finish = getattr(resp, "finish_reason", None) or (
        "tool_calls" if tool_calls else "stop"
    )
    out: Dict[str, Any] = {
        "id": cmpl_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_out,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish,
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        },
    }
    # 可选：透出计费档（自动降级 shared 时便于客户端提示充值）
    attr = getattr(resp, "attribution", None) or {}
    if isinstance(attr, dict) and attr.get("billing_mode"):
        out["ai24x"] = {
            "billing_mode": attr.get("billing_mode"),
            "auto_degraded": bool(attr.get("auto_degraded")),
            "upgrade_hint": attr.get("upgrade_hint_en") or attr.get("upgrade_hint_zh"),
        }
    return out


def _chunk_text(text: str, size: int = 24) -> List[str]:
    s = text or ""
    if not s:
        return [""]
    return [s[i : i + size] for i in range(0, len(s), size)]


def iter_sse_from_completion(resp: ChatResponse, *, requested_model: str, cmpl_id: str) -> Iterator[str]:
    """将已完成的回复切成 OpenAI SSE chunk（计费已在上游完成）。"""
    model_out = resp.model or requested_model or "flash"
    created = int(time.time())
    tool_calls = getattr(resp, "tool_calls", None)
    finish = getattr(resp, "finish_reason", None) or (
        "tool_calls" if tool_calls else "stop"
    )

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
    if tool_calls:
        # 假流式：整包 tool_calls（真流式走 iter_true_sse）
        yield pack(
            {
                "id": cmpl_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_out,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": tool_calls},
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
                    "finish_reason": finish,
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


def iter_true_sse_from_events(
    events: Iterator[Dict[str, Any]],
    *,
    requested_model: str,
    cmpl_id: str,
) -> Iterator[str]:
    """把 ChatService.stream_chat_request 事件打成 OpenAI SSE。"""
    model_out = requested_model or "flash"
    created = int(time.time())
    role_sent = False

    def pack(payload: Dict[str, Any]) -> str:
        return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

    def ensure_role() -> Iterator[str]:
        nonlocal role_sent
        if role_sent:
            return
        role_sent = True
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

    for ev in events:
        et = ev.get("type")
        if et == "meta":
            model_out = str(ev.get("public_model") or ev.get("raw_model") or model_out)
            continue
        if et == "error":
            err = str(ev.get("error") or "upstream_error")
            # 用户可读短句（避免堆栈/上游原文）
            if err in ("tools_unsupported", "vip_required", "tools_need_balance"):
                if err == "vip_required":
                    msg = "VIP required for this model."
                elif err == "tools_need_balance":
                    msg = "Tool calling needs available credit balance. Please top up."
                else:
                    msg = "This model cannot use tools right now. Try flash or pro."
            else:
                msg = "Service temporarily unavailable. Please try again."
            yield pack(
                {
                    "id": cmpl_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_out,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": ""},
                            "finish_reason": "stop",
                        }
                    ],
                    "error": {"message": msg, "type": "server_error"},
                }
            )
            yield "data: [DONE]\n\n"
            return
        if et == "delta":
            yield from ensure_role()
            piece = str(ev.get("text") or "")
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
        if et == "tool_calls_delta":
            yield from ensure_role()
            tcs = ev.get("tool_calls")
            if not tcs:
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
                            "delta": {"tool_calls": tcs},
                            "finish_reason": None,
                        }
                    ],
                }
            )
        if et == "done":
            yield from ensure_role()
            model_out = str(ev.get("public_model") or model_out)
            finish = str(ev.get("finish_reason") or "stop")
            # 若流中未增量发过 tool_calls，收尾包补发整包（兼容部分上游）
            final_tcs = ev.get("tool_calls")
            if final_tcs and not ev.get("tool_calls_streamed"):
                yield pack(
                    {
                        "id": cmpl_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_out,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"tool_calls": final_tcs},
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
                            "finish_reason": finish,
                        }
                    ],
                }
            )
            yield "data: [DONE]\n\n"
            return
    yield "data: [DONE]\n\n"


def true_streaming_response(
    events: Iterator[Dict[str, Any]],
    *,
    requested_model: str,
    cmpl_id: str,
) -> StreamingResponse:
    return StreamingResponse(
        iter_true_sse_from_events(
            events, requested_model=requested_model, cmpl_id=cmpl_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# OpenAI Responses API 最小兼容（LobeChat / Continue 等默认走 /v1/responses）
# 复用 ChatService；文本最小兼容。tools / 多模态 / 持久化仍不在 Responses 路径。
# ---------------------------------------------------------------------------


def response_id() -> str:
    return "resp_" + uuid.uuid4().hex


def _msg_id() -> str:
    return "msg_" + uuid.uuid4().hex


def _input_part_to_text(part: Any) -> str:
    if part is None:
        return ""
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return str(part)
    t = str(part.get("type") or "").strip().lower()
    if t in ("input_text", "output_text", "text") or "text" in part:
        return str(part.get("text") or "")
    if t == "input_image" or "image_url" in part:
        return "[image]"
    return _content_to_text(part.get("content") if "content" in part else part)


def responses_input_to_messages(body: Dict[str, Any]) -> List[Dict[str, str]]:
    """Responses `input` (+ optional `instructions`) → chat messages[]."""
    messages: List[Dict[str, str]] = []
    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions.strip()})

    raw = body.get("input")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="input 不能为空",
        )
    if isinstance(raw, str):
        if not raw.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="input 不能为空",
            )
        messages.append({"role": "user", "content": raw.strip()})
        return messages
    if not isinstance(raw, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="input 须为字符串或数组",
        )

    for item in raw:
        if isinstance(item, str):
            if item.strip():
                messages.append({"role": "user", "content": item.strip()})
            continue
        if not isinstance(item, dict):
            continue
        itype = str(item.get("type") or "").strip().lower()
        if itype in ("function_call", "function_call_output", "reasoning", "web_search_call"):
            continue
        role = str(item.get("role") or "user").strip().lower()
        if role in ("tool", "function"):
            continue
        content = item.get("content")
        if isinstance(content, list):
            text = "\n".join(
                x for x in (_input_part_to_text(p) for p in content) if x
            ).strip()
        else:
            text = _content_to_text(content).strip()
        if not text and isinstance(item.get("text"), str):
            text = item["text"].strip()
        if not text:
            continue
        if role not in ("system", "assistant", "user", "developer"):
            role = "user"
        if role == "developer":
            role = "system"
        messages.append({"role": role, "content": text})

    if not messages or all(m.get("role") == "system" for m in messages):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="input 中无有效用户文本",
        )
    return messages


def build_chat_request_from_responses(body: Dict[str, Any]) -> ChatRequestSchema:
    """把 Responses 请求体转成内部 ChatRequest。"""
    messages = responses_input_to_messages(body)
    model = map_model_name(body.get("model"))
    try:
        temperature = float(
            body.get("temperature") if body.get("temperature") is not None else 0.7
        )
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(2.0, temperature))
    max_raw = body.get("max_output_tokens")
    if max_raw is None:
        max_raw = body.get("max_tokens")
    try:
        max_tokens = int(max_raw if max_raw is not None else 1000)
    except (TypeError, ValueError):
        max_tokens = 1000
    max_tokens = max(1, min(4000, max_tokens))
    return ChatRequestSchema(
        prompt=messages_to_prompt(messages),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=bool(body.get("stream")),
    )


def to_openai_response(
    resp: ChatResponse, *, requested_model: str, resp_id: str
) -> Dict[str, Any]:
    total = max(0, int(resp.token_count or 0))
    prompt_tokens = max(1, int(total * 0.3)) if total else 0
    completion_tokens = max(0, total - prompt_tokens) if total else 0
    model_out = resp.model or requested_model or "flash"
    text = resp.response or ""
    mid = _msg_id()
    out: Dict[str, Any] = {
        "id": resp_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": model_out,
        "output": [
            {
                "id": mid,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": text,
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": total,
        },
    }
    attr = getattr(resp, "attribution", None) or {}
    if isinstance(attr, dict) and attr.get("billing_mode"):
        out["ai24x"] = {
            "billing_mode": attr.get("billing_mode"),
            "auto_degraded": bool(attr.get("auto_degraded")),
            "upgrade_hint": attr.get("upgrade_hint_en") or attr.get("upgrade_hint_zh"),
        }
    return out


def iter_sse_from_response(
    resp: ChatResponse, *, requested_model: str, resp_id: str
) -> Iterator[str]:
    """最小 Responses SSE：output_text.delta + completed（计费已在上游完成）。"""
    model_out = resp.model or requested_model or "flash"
    created = int(time.time())
    mid = _msg_id()
    text = resp.response or ""
    total = max(0, int(resp.token_count or 0))
    prompt_tokens = max(1, int(total * 0.3)) if total else 0
    completion_tokens = max(0, total - prompt_tokens) if total else 0

    def pack(event: str, payload: Dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    base = {
        "id": resp_id,
        "object": "response",
        "created_at": created,
        "status": "in_progress",
        "model": model_out,
        "output": [],
    }
    yield pack("response.created", {"type": "response.created", "response": dict(base)})
    yield pack(
        "response.output_item.added",
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "id": mid,
                "type": "message",
                "status": "in_progress",
                "role": "assistant",
                "content": [],
            },
        },
    )
    yield pack(
        "response.content_part.added",
        {
            "type": "response.content_part.added",
            "item_id": mid,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": []},
        },
    )
    for piece in _chunk_text(text, 32):
        if not piece:
            continue
        yield pack(
            "response.output_text.delta",
            {
                "type": "response.output_text.delta",
                "item_id": mid,
                "output_index": 0,
                "content_index": 0,
                "delta": piece,
            },
        )
    yield pack(
        "response.output_text.done",
        {
            "type": "response.output_text.done",
            "item_id": mid,
            "output_index": 0,
            "content_index": 0,
            "text": text,
        },
    )
    completed = to_openai_response(resp, requested_model=requested_model, resp_id=resp_id)
    completed["created_at"] = created
    if completed.get("output") and isinstance(completed["output"][0], dict):
        completed["output"][0]["id"] = mid
    completed["usage"] = {
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "total_tokens": total,
    }
    yield pack(
        "response.completed",
        {"type": "response.completed", "response": completed},
    )


def streaming_responses_response(
    resp: ChatResponse, *, requested_model: str, resp_id: str
) -> StreamingResponse:
    return StreamingResponse(
        iter_sse_from_response(resp, requested_model=requested_model, resp_id=resp_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
