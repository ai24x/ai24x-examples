"""AI24X Markets connectivity test — quote / kline / signals across symbols.

Usage: python _test_connectivity.py [base_url]
Default base: http://127.0.0.1:18012
"""

import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18012"

GROUPS = {
    "stocks": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "BRK.A", "BABA", "NIO"],
    "etfs": ["SPY", "QQQ", "DIA", "ARKK", "VTI"],
    "indices": ["^GSPC", "^IXIC", "^DJI", "^VIX"],
    "variants": ["aapl", "usAAPL", "spy"],
    "invalid": ["ZZZZ"],
}


def main() -> int:
    client = httpx.Client(timeout=20.0)
    results = []
    fail_total = 0

    for group, symbols in GROUPS.items():
        for sym in symbols:
            q = _probe(client, "quote", sym)
            k = _probe(client, "kline", sym)
            s = _probe(client, "signals", sym) if group in ("stocks", "indices") and sym in (
                "AAPL", "TSLA", "NVDA", "^GSPC", "^IXIC", "BRK.A", "SPY") else None
            ok = q[0] and k[0] and (s is None or s[0])
            if not ok:
                fail_total += 1
            results.append((group, sym, q, k, s, ok))

    print(f"== AI24X Markets connectivity @ {BASE} ==")
    print(f"{'GROUP':9} {'SYMBOL':8} {'QUOTE':6} {'KLINE':6} {'SIG':5} RESULT")
    for group, sym, q, k, s, ok in results:
        print(
            f"{group:9} {sym:8} {('OK' if q[0] else 'FAIL'):6} "
            f"{('OK' if k[0] else 'FAIL'):6} {('OK' if s and s[0] else ('-' if s is None else 'FAIL')):5} "
            f"{'PASS' if ok else 'FAIL'}"
        )
    print(f"TOTAL={len(results)} FAIL={fail_total}")

    # detail dump for failures
    for group, sym, q, k, s, ok in results:
        if not ok:
            print(f"--- {group} {sym} ---")
            for name, r in (("quote", q), ("kline", k), ("signals", s)):
                if r is not None and not r[0]:
                    print(f"  {name}: {json.dumps(r[1], ensure_ascii=False)[:300]}")
    return 1 if fail_total else 0


def _probe(client: httpx.Client, kind: str, symbol: str):
    """Return (ok, payload) or None."""
    path = f"/api/{kind}"
    params = {"symbol": symbol}
    if kind == "kline":
        params.update({"period": "day", "count": 120})
    try:
        r = client.get(BASE + path, params=params)
        body = r.json()
        if r.status_code != 200:
            return (False, {"http": r.status_code})
        if body.get("code") != 0:
            return (False, body)
        data = body.get("data") or {}
        if kind == "quote":
            ok = bool(data.get("price"))
        elif kind == "kline":
            ok = bool(data.get("candles"))
        else:
            ok = bool(data.get("candles") or data.get("signals") or data.get("summary"))
        return (ok, data)
    except Exception as e:
        return (False, {"err": str(e)})


if __name__ == "__main__":
    sys.exit(main())
