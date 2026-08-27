import json
import sys

paths = [
    r"C:\ai24x01\api\data\token_plans_override.json",
    r"C:\ai24x01\p\open\api\data\token_plans_override.json",
]

note_zh = (
    "\u5c0f\u989d\u4f53\u9a8c\u5305\uff1a$0.1 \u8bd5\u6c34 100 \u4e07 "
    "token\uff08\u7ea6\u6570\u5343\u6b21 flash \u8c03\u7528\uff09\u3002"
    "\u4ec5\u9884\u5145\u989d\u5ea6\uff0c\u4e0d\u542b\u540d\u6a21\u8d44\u683c\uff1b"
    "\u8981\u70b9\u540d\u8bf7\u9009 Scale\u3002\u989d\u5ea6 12 \u4e2a\u6708\u6709\u6548\u3002"
)
note_en = (
    "Starter trial: $0.1 for 1M credits (~thousands of flash calls). "
    "Credits only\u2014no named-model access; choose Scale to name models. Valid 12 months."
)

for path in paths:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    plan = data.get("plans", {}).get("token_pack_10k", {})
    old_usd = plan.get("price_usd")
    old_fen = plan.get("price_fen")
    plan["price_usd"] = 0.1
    plan["price_fen"] = 72
    plan["note_en"] = note_en
    plan["note_zh"] = note_zh
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(
        "patched " + path
        + " | price_usd " + str(old_usd) + " -> 0.1"
        + " | price_fen " + str(old_fen) + " -> 72"
        + " | dodo_product_id kept: " + str(plan.get("dodo_product_id"))
    )

print("DONE")
