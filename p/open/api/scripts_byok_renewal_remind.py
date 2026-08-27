#!/usr/bin/env python3
"""BYOK Pro renewal reminder runner (open-api).

  cd p/open/api
  python scripts_byok_renewal_remind.py           # dry-run
  python scripts_byok_renewal_remind.py --apply   # send mail
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="BYOK Pro renewal reminders")
    parser.add_argument("--apply", action="store_true", help="Actually send emails")
    parser.add_argument("--lang", default="en", choices=("en", "zh"))
    args = parser.parse_args()

    from database import SessionLocal
    from byok_renewal import run_renewal_reminders

    db = SessionLocal()
    try:
        result = run_renewal_reminders(db=db, apply=bool(args.apply), lang=args.lang)
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if int(result.get("failed") or 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
