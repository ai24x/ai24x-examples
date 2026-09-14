import os
import sys
import traceback

api_dir = os.environ.get("AI24X_API_DIR") or r"C:\ai24x01\api"
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)
os.chdir(api_dir)

# Load .env like the service
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(api_dir, ".env"))
except Exception as e:
    print("dotenv skip", e)

steps = [
    ("billing_money", lambda: __import__("billing_money")),
    ("token_pay_service", lambda: __import__("token_pay_service")),
    ("public_plans", lambda: __import__("token_pay_service").public_plans()),
    ("pay_products", lambda: __import__("pay_products").public_products()),
]

for name, fn in steps:
    try:
        r = fn()
        if name == "public_plans":
            print(name, "OK", len((r or {}).get("plans") or []))
        elif name == "pay_products":
            print(name, "OK", len((r or {}).get("products") or []))
        else:
            print(name, "OK")
    except Exception:
        print("FAIL", name)
        traceback.print_exc()
        raise SystemExit(1)

# Hit local HTTP like nginx
try:
    import urllib.request

    for path in ("/v1/billing/plans", "/v1/billing/products"):
        url = "http://127.0.0.1:8002" + path
        try:
            resp = urllib.request.urlopen(url, timeout=15)
            body = resp.read(200)
            print("HTTP", path, resp.status, body[:120])
        except Exception as e:
            code = getattr(e, "code", None)
            body = e.read(200) if hasattr(e, "read") else b""
            print("HTTP", path, code, body[:120])
except Exception:
    traceback.print_exc()
