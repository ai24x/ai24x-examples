"""主站 Token 人工工单（平台客服异步队列）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from models import AuthUser, SupportTicket, SupportTicketMessage

_ALLOWED_CAT = {"billing", "api", "account", "suggestion", "complaint"}
_ALLOWED_STATUS = {"open", "replied", "closed"}


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _row(t: SupportTicket, *, include_user: bool = False, user: Optional[AuthUser] = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": int(t.id),
        "auth_user_id": int(t.auth_user_id),
        "category": t.category,
        "subject": t.subject or "",
        "body": t.body or "",
        "ai_summary": t.ai_summary,
        "status": t.status,
        "admin_reply": t.admin_reply,
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }
    if include_user and user is not None:
        d["user"] = {
            "id": int(user.id),
            "email": user.email or "",
            "phone": user.phone or "",
        }
    return d


def _msg_row(m: SupportTicketMessage) -> dict[str, Any]:
    return {
        "id": int(m.id),
        "sender": m.sender,
        "content": m.content or "",
        "created_at": _iso(m.created_at),
    }


def _ai_reply(auth_user_id: int, question: str, lang_hint: str = "en") -> Optional[str]:
    """AI 自动回复（平台侧，不扣用户余额）；失败/超限返回 None（工单不受影响）。"""
    try:
        from support_bot import ask_support

        r = ask_support(auth_user_id=int(auth_user_id), question=question, lang_hint=lang_hint)
        txt = str((r or {}).get("answer") or "").strip()
        return txt[:4000] or None
    except Exception:
        return None


def _append_msg(db: Session, *, ticket_id: int, sender: str, content: str) -> SupportTicketMessage:
    row = SupportTicketMessage(
        ticket_id=int(ticket_id),
        sender=str(sender)[:16],
        content=str(content or "")[:4000],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_ticket(
    db: Session,
    *,
    auth_user_id: int,
    category: str,
    body: str,
    subject: str = "",
    ai_summary: Optional[str] = None,
) -> dict[str, Any]:
    cat = (category or "api").strip().lower()
    if cat not in _ALLOWED_CAT:
        cat = "api"
    text = (body or "").strip()
    if len(text) < 10:
        return {"ok": False, "message": "请把问题写清楚一些（至少 10 个字）。"}
    if len(text) > 4000:
        text = text[:4000]
    sub = (subject or "").strip()[:120]
    if not sub:
        sub = text[:40]
    # 每用户每日开单上限，防刷
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_n = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.auth_user_id == int(auth_user_id),
            SupportTicket.created_at >= day_start,
        )
        .count()
    )
    if today_n >= 8:
        return {"ok": False, "message": "今日提交次数已达上限，请明天再试或查阅帮助中心。"}

    row = SupportTicket(
        auth_user_id=int(auth_user_id),
        category=cat,
        subject=sub,
        body=text,
        ai_summary=(ai_summary or "").strip()[:2000] or None,
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # 多轮会话：写入首条用户消息 + AI 自动回复（即时互动）
    _append_msg(db, ticket_id=int(row.id), sender="user", content=text)
    ai = _ai_reply(int(auth_user_id), text, lang_hint="zh")
    if ai:
        _append_msg(db, ticket_id=int(row.id), sender="system", content=ai)
    return {"ok": True, "ticket": _row(row)}


def list_tickets_for_user(
    db: Session, auth_user_id: int, *, limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    q = db.query(SupportTicket).filter(SupportTicket.auth_user_id == int(auth_user_id))
    total = q.count()
    rows = (
        q.order_by(SupportTicket.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(50, max(1, int(limit))))
        .all()
    )
    out = []
    for r in rows:
        d = _row(r)
        last = (
            db.query(SupportTicketMessage)
            .filter(SupportTicketMessage.ticket_id == int(r.id))
            .order_by(SupportTicketMessage.id.desc())
            .first()
        )
        if last is not None:
            d["last_message"] = last.content[:120]
            d["last_sender"] = last.sender
            d["last_at"] = _iso(last.created_at)
        out.append(d)
    return {"total": total, "rows": out}


def get_ticket_detail(db: Session, auth_user_id: int, ticket_id: int) -> dict[str, Any]:
    """工单详情：工单信息 + 完整对话消息（按时间正序）。"""
    row = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.id == int(ticket_id),
            SupportTicket.auth_user_id == int(auth_user_id),
        )
        .first()
    )
    if not row:
        return {"ok": False, "message": "工单不存在"}
    msgs = (
        db.query(SupportTicketMessage)
        .filter(SupportTicketMessage.ticket_id == int(row.id))
        .order_by(SupportTicketMessage.id.asc())
        .all()
    )
    d = _row(row)
    d["messages"] = [_msg_row(m) for m in msgs]
    return {"ok": True, "ticket": d}


def user_reply_ticket(
    db: Session, auth_user_id: int, ticket_id: int, content: str
) -> dict[str, Any]:
    """用户追加消息 → 系统 AI 自动回复（多轮会话）。"""
    row = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.id == int(ticket_id),
            SupportTicket.auth_user_id == int(auth_user_id),
        )
        .first()
    )
    if not row:
        return {"ok": False, "message": "工单不存在"}
    text = (content or "").strip()
    if len(text) < 1:
        return {"ok": False, "message": "请填写消息内容"}
    if len(text) > 4000:
        text = text[:4000]
    _append_msg(db, ticket_id=int(row.id), sender="user", content=text)
    row.status = "open"
    db.commit()
    ai = _ai_reply(int(auth_user_id), text, lang_hint="zh")
    if ai:
        _append_msg(db, ticket_id=int(row.id), sender="system", content=ai)
    return get_ticket_detail(db, int(auth_user_id), int(ticket_id))


def admin_list_tickets(
    db: Session,
    *,
    status: Optional[str] = None,
    category: Optional[str] = None,
    auth_user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    q = db.query(SupportTicket, AuthUser).outerjoin(
        AuthUser, AuthUser.id == SupportTicket.auth_user_id
    )
    st = (status or "").strip().lower()
    if st in _ALLOWED_STATUS:
        q = q.filter(SupportTicket.status == st)
    cat = (category or "").strip().lower()
    if cat in _ALLOWED_CAT:
        q = q.filter(SupportTicket.category == cat)
    if auth_user_id:
        q = q.filter(SupportTicket.auth_user_id == int(auth_user_id))
    total = q.count()
    pairs = (
        q.order_by(SupportTicket.id.desc())
        .offset(max(0, int(offset)))
        .limit(min(200, max(1, int(limit))))
        .all()
    )
    return {
        "total": total,
        "rows": [_row(t, include_user=True, user=u) for t, u in pairs],
    }


def admin_reply_ticket(
    db: Session, *, ticket_id: int, reply: str, close: bool = False
) -> dict[str, Any]:
    row = db.query(SupportTicket).filter(SupportTicket.id == int(ticket_id)).first()
    if not row:
        return {"ok": False, "message": "工单不存在"}
    text = (reply or "").strip()
    if len(text) < 1:
        return {"ok": False, "message": "请填写回复内容"}
    row.admin_reply = text[:4000]
    row.status = "closed" if close else "replied"
    db.commit()
    db.refresh(row)
    # 多轮会话：人工回复同步写入消息流
    _append_msg(db, ticket_id=int(row.id), sender="admin", content=text)
    return {"ok": True, "ticket": _row(row)}
