# -*- coding: utf-8 -*-
"""付费广告 / 渠道 UTM 规范化（注册首触落库；充值用 auth_user_id join）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models import AuthUser

_MAX = 128
_KEYS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "gclid",
)


def _clean(val: Any, *, max_len: int = _MAX) -> str:
    s = str(val or "").strip()
    if not s:
        return ""
    # 去掉控制字符与空白折叠
    s = "".join(ch for ch in s if ord(ch) >= 32)
    s = " ".join(s.split())
    return s[:max_len]


def normalize_acquisition(raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """从注册 body / 前端 payload 抽出可落库字段。"""
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, str] = {}
    for k in _KEYS:
        v = _clean(src.get(k))
        if v:
            out[k] = v
    return out


def user_has_acquisition(user: AuthUser) -> bool:
    return bool(
        (getattr(user, "utm_source", None) or "").strip()
        or (getattr(user, "gclid", None) or "").strip()
    )


def apply_acquisition_on_register(
    db: Session,
    user: AuthUser,
    raw: Optional[Dict[str, Any]],
) -> bool:
    """
    首触写入：已有 utm_source/gclid 则不覆盖。
    返回是否写入了新字段。
    """
    attrs = normalize_acquisition(raw)
    if not attrs:
        return False
    if user_has_acquisition(user):
        return False
    for k, v in attrs.items():
        setattr(user, k, v)
    if getattr(user, "acquired_at", None) is None:
        user.acquired_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return True


def acquisition_public_dict(user: Optional[AuthUser]) -> Dict[str, Any]:
    if not user:
        return {}
    return {
        "utm_source": (getattr(user, "utm_source", None) or "") or None,
        "utm_medium": (getattr(user, "utm_medium", None) or "") or None,
        "utm_campaign": (getattr(user, "utm_campaign", None) or "") or None,
        "utm_content": (getattr(user, "utm_content", None) or "") or None,
        "utm_term": (getattr(user, "utm_term", None) or "") or None,
        "gclid": (getattr(user, "gclid", None) or "") or None,
        "acquired_at": user.acquired_at.isoformat()
        if getattr(user, "acquired_at", None)
        else None,
    }
