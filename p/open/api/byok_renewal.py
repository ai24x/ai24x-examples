"""
BYOK Pro 续费提醒（Phase 2）。

- 到期前 7 / 3 / 1 天各发一次邮件（有邮箱且 SMTP 可用时）
- 去重：本地 JSON 状态文件（不依赖 Redis；跨机需共享 data 或改 Redis）
- 控制台另有 days_left 横幅（无邮件也能提醒）

用法：
  python scripts_byok_renewal_remind.py           # dry-run
  python scripts_byok_renewal_remind.py --apply   # 真正发信
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 到期前第 N 天触发（按 UTC 日历日 floor(days_left)）
REMIND_WINDOWS = (7, 3, 1)

_STATE_NAME = "byok_renewal_sent.json"


def _state_path() -> Path:
    try:
        from config import settings

        base = Path(getattr(settings, "data_dir", "") or "").resolve()
        if not base.is_dir():
            base = Path(__file__).resolve().parent / "data"
    except Exception:
        base = Path(__file__).resolve().parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / _STATE_NAME


def _load_state() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {"sent": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("sent"), dict):
            return data
    except Exception:
        pass
    return {"sent": {}}


def _save_state(data: dict[str, Any]) -> None:
    p = _state_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _dedupe_key(auth_user_id: int, expires_at: datetime, window: int) -> str:
    exp = expires_at.astimezone(timezone.utc).date().isoformat()
    return f"{int(auth_user_id)}:{exp}:d{int(window)}"


def _renew_url() -> str:
    try:
        from config import settings

        base = str(getattr(settings, "public_web_base", "") or "").rstrip("/")
        if base:
            return f"{base}/console.html#byok"
    except Exception:
        pass
    return "https://open.ai24x.com/console.html#byok"


def _compose_mail(*, plan: str, expires_at: datetime, days_left: int, lang: str = "en") -> tuple[str, str]:
    exp = expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    url = _renew_url()
    plan_label = "BYOK Pro Yearly" if "year" in (plan or "").lower() else "BYOK Pro Monthly"
    if (lang or "").lower().startswith("zh"):
        subject = f"【AI24X】BYOK Pro 将于 {exp} 到期（还剩 {days_left} 天）"
        body = (
            f"你好，\n\n"
            f"你的 {plan_label} 将于 {exp}（UTC）到期，还剩约 {days_left} 天。\n"
            f"到期后会回到免费档（每月有限次请求）。续费后从当前到期日顺延，不中断。\n\n"
            f"续费入口：{url}\n\n"
            f"— AI24X\n"
        )
    else:
        subject = f"AI24X · BYOK Pro renews soon ({days_left} day(s) left)"
        body = (
            f"Hi,\n\n"
            f"Your {plan_label} expires on {exp} UTC (~{days_left} day(s) left).\n"
            f"After expiry you return to the free tier (monthly request cap). "
            f"Renewing extends from your current expiry date.\n\n"
            f"Renew here: {url}\n\n"
            f"— AI24X\n"
        )
    return subject, body


def list_due_reminders(db) -> list[dict[str, Any]]:
    """扫描即将到期的 active 订阅，返回待提醒行（未做去重过滤）。"""
    from models import AuthUser, ByokSubscription

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=max(REMIND_WINDOWS) + 1)
    rows = (
        db.query(ByokSubscription, AuthUser)
        .outerjoin(AuthUser, AuthUser.id == ByokSubscription.auth_user_id)
        .filter(
            ByokSubscription.status == "active",
            ByokSubscription.expires_at > now,
            ByokSubscription.expires_at <= horizon,
        )
        .all()
    )
    out: list[dict[str, Any]] = []
    for sub, user in rows:
        if not sub.expires_at:
            continue
        exp = sub.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        days_left = int((exp - now).total_seconds() // 86400)
        if days_left not in REMIND_WINDOWS:
            continue
        email = (getattr(user, "email", None) or "").strip() if user else ""
        out.append(
            {
                "auth_user_id": int(sub.auth_user_id),
                "email": email,
                "plan": str(sub.plan or ""),
                "expires_at": exp,
                "days_left": days_left,
                "dedupe_key": _dedupe_key(int(sub.auth_user_id), exp, days_left),
            }
        )
    return out


def run_renewal_reminders(*, db, apply: bool = False, lang: str = "en") -> dict[str, Any]:
    """
    跑一轮续费提醒。
    apply=False：只统计；apply=True：发信并写去重状态。
    """
    from email_smtp import send_text_email, smtp_backup_configured, smtp_configured

    state = _load_state()
    sent_map: dict[str, Any] = state.setdefault("sent", {})
    due = list_due_reminders(db)
    mail_ready = smtp_configured() or smtp_backup_configured()

    summary: dict[str, Any] = {
        "apply": bool(apply),
        "mail_ready": mail_ready,
        "windows": list(REMIND_WINDOWS),
        "candidates": len(due),
        "skipped_no_email": 0,
        "skipped_dedupe": 0,
        "would_send": 0,
        "sent": 0,
        "failed": 0,
        "errors": [],
    }

    for row in due:
        key = row["dedupe_key"]
        if key in sent_map:
            summary["skipped_dedupe"] += 1
            continue
        if not row["email"]:
            summary["skipped_no_email"] += 1
            continue
        summary["would_send"] += 1
        if not apply:
            continue
        if not mail_ready:
            summary["failed"] += 1
            summary["errors"].append({"id": row["auth_user_id"], "error": "mail_unavailable"})
            continue
        subject, body = _compose_mail(
            plan=row["plan"],
            expires_at=row["expires_at"],
            days_left=int(row["days_left"]),
            lang=lang,
        )
        ok, msg = send_text_email(to_email=row["email"], subject=subject, body=body)
        if ok:
            summary["sent"] += 1
            sent_map[key] = {
                "at": datetime.now(timezone.utc).isoformat(),
                "email": row["email"][:3] + "***",
                "days_left": row["days_left"],
            }
        else:
            summary["failed"] += 1
            summary["errors"].append({"id": row["auth_user_id"], "error": str(msg)[:120]})
            logger.warning("BYOK renewal mail failed uid=%s: %s", row["auth_user_id"], msg)

    if apply:
        # 清理过旧去重键（保留约 60 天）
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        prune = []
        for k, v in list(sent_map.items()):
            try:
                at = datetime.fromisoformat(str((v or {}).get("at") or "").replace("Z", "+00:00"))
                if at < cutoff:
                    prune.append(k)
            except Exception:
                prune.append(k)
        for k in prune:
            sent_map.pop(k, None)
        _save_state(state)

    return summary
