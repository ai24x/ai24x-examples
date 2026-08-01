"""用户可见错误：双语 detail，供前端按界面语言选取。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def user_detail(zh: str, en: str, *, code: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"message_zh": zh, "message_en": en, "message": zh}
    if code:
        out["code"] = code
    return out


def raise_user(status_code: int, zh: str, en: str, *, code: str = "") -> None:
    raise HTTPException(status_code=status_code, detail=user_detail(zh, en, code=code))
