# -*- coding: utf-8 -*-
from database import SessionLocal
from ops_alert import run_check, reset_state
reset_state()
db = SessionLocal()
try:
    r = run_check(db, push=True)
    print("pushed =", r.get("pushed"))
    print("new_push =", [a.get("code") for a in r.get("new_push", [])])
    print("recovered =", r.get("recovered"))
    print("alerts =", [(a.get("level"), a.get("code")) for a in r.get("alerts", [])])
finally:
    db.close()
