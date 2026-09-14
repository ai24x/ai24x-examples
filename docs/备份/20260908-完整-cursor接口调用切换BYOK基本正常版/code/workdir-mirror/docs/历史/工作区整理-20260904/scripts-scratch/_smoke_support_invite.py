# -*- coding: utf-8 -*-
"""本机冒烟：短链 / support ask / tickets / admin referrals（需本地库）。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method: str, path: str, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read()
            return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    rows = []
    # health
    st, _ = req("GET", "/health")
    rows.append(("health", st == 200, st))
    # short link
    st, raw = req("GET", "/r/ABCD1234")
    # urllib follows redirect by default — check final or use no redirect
    rows.append(("short_link_get", st in (200, 302), st))
    # support ask no auth
    st, raw = req("POST", "/v1/support/ask", {"question": "how to use flash"})
    rows.append(("support_ask_401", st == 401, st))
    # tickets no auth
    st, _ = req("POST", "/v1/support/tickets", {"category": "api", "body": "hello world test ticket body"})
    rows.append(("tickets_401", st == 401, st))
    # admin referrals no key
    st, _ = req("GET", "/v1/admin/token/referrals")
    rows.append(("admin_ref_no_key", st in (403, 503), st))
    st, _ = req("GET", "/v1/admin/token/tickets")
    rows.append(("admin_tk_no_key", st in (403, 503), st))

    ok = all(x[1] for x in rows)
    for name, good, code in rows:
        print(("OK" if good else "FAIL"), name, code)
    print("SMOKE_" + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    # disable redirect follow for short link check
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    urllib.request.install_opener(opener)
    sys.exit(main())
