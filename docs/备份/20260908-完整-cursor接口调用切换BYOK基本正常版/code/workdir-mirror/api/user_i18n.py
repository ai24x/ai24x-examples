"""用户可见错误：双语 detail，供前端按界面语言选取。"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from fastapi import HTTPException


def user_detail(zh: str, en: str, *, code: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"message_zh": zh, "message_en": en, "message": zh}
    if code:
        out["code"] = code
    return out


def raise_user(status_code: int, zh: str, en: str, *, code: str = "") -> None:
    raise HTTPException(status_code=status_code, detail=user_detail(zh, en, code=code))


def is_bilingual_detail(detail: object) -> bool:
    return isinstance(detail, dict) and (
        "message_zh" in detail or "message_en" in detail or "message" in detail
    )


def flatten_http_detail(detail: object) -> Tuple[str, Optional[object]]:
    """把 HTTPException.detail 压成用户可读字符串，并保留结构化 detail（若有）。

    禁止对双语 dict 使用 str(dict)（会把 message_zh 整包漏到前端）。
    """
    if detail is None:
        return "error", None
    if isinstance(detail, str):
        return detail, detail
    if is_bilingual_detail(detail):
        d = detail  # type: ignore[assignment]
        zh = str(d.get("message_zh") or d.get("message") or "").strip()
        en = str(d.get("message_en") or "").strip()
        return (zh or en or "error"), d
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                m = item.get("msg") or item.get("message")
                if m:
                    parts.append(str(m))
            elif item is not None:
                parts.append(str(item))
        return ("；".join(parts) if parts else "参数无效，请检查后再试。"), detail
    # 其它类型：尽量不把 repr 漏给用户
    return "参数无效，请检查后再试。", None


def openai_user_message(detail: object) -> str:
    """OpenAI 兼容错误体用英文优先的短句。"""
    text, structured = flatten_http_detail(detail)
    if is_bilingual_detail(structured):
        d = structured  # type: ignore[assignment]
        en = str(d.get("message_en") or "").strip()
        if en:
            return en
    return text