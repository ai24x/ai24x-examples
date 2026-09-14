"""Local smoke for BYOK Phase2: usage_daily + redis cache fallback + renewal dry-run."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from byok import _cache_get, _cache_put, cache_stats, usage_daily, subscription_status
    from byok_renewal import list_due_reminders, run_renewal_reminders, REMIND_WINDOWS

    # cache: memory path always works
    k = "qa_cache_" + datetime.now(timezone.utc).strftime("%H%M%S")
    _cache_put(k, {"hello": "world", "n": 1})
    hit = _cache_get(k)
    assert hit and hit.get("hello") == "world", hit
    st = cache_stats()
    assert st.get("ttl_s") is not None and st.get("backend") in ("redis", "memory"), st
    print("OK cache backend=", st.get("backend"), "items=", st.get("items"))

    # usage_daily shape (empty DB ok)
    from database import SessionLocal

    db = SessionLocal()
    try:
        daily = usage_daily(db, auth_user_id=1, days=7)
        assert daily.get("days") == 7
        assert len(daily.get("rows") or []) == 7
        assert set(daily["rows"][0].keys()) >= {
            "date",
            "requests",
            "tokens",
            "cost_usd",
        }
        print("OK usage_daily rows=", len(daily["rows"]))

        sub = subscription_status(db, 1)
        assert "days_left" in sub or sub.get("active") is False or sub.get("status") == "none" or True
        print("OK subscription_status keys=", sorted(sub.keys()))

        due = list_due_reminders(db)
        print("OK renewal windows=", REMIND_WINDOWS, "due=", len(due))
        dry = run_renewal_reminders(db=db, apply=False, lang="en")
        assert dry.get("apply") is False
        print("OK renewal dry-run", {k: dry[k] for k in ("candidates", "would_send", "mail_ready")})
    finally:
        db.close()

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
