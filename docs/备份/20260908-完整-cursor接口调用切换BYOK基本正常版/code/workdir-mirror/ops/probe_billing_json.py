import json
import os
import sys

api_dir = r"C:\ai24x01\api"
sys.path.insert(0, api_dir)
os.chdir(api_dir)
from dotenv import load_dotenv
load_dotenv(os.path.join(api_dir, ".env"))
from token_pay_service import public_plans
from pay_products import public_products
p = public_plans()
json.dumps(p)
print("public_plans json OK", len(p.get("plans") or []))
pp = public_products()
json.dumps(pp)
print("public_products json OK", len(pp.get("products") or []))
