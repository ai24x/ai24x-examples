import os
import sys
import traceback

api_dir = os.environ.get("AI24X_API_DIR") or r"C:\ai24x01\api"
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)
os.chdir(api_dir)

try:
    from token_pay_service import public_plans
    p = public_plans()
    print("OK plans", len(p.get("plans") or []))
except Exception:
    traceback.print_exc()
    raise SystemExit(1)
