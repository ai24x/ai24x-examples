# -*- coding: utf-8 -*-
"""Tools-support probe for all display models (vip picks + brand tiers).
Uses production chain (model_router._vip_aggregator_chain / _layer_upstream)
and calls the first working upstream with a tool-calling request.
Output: JSON result file + console summary.
2026-08-13 副脑04
"""
import sys, json, time, urllib.request, urllib.error

sys.path.insert(0, ".")
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(".env"))

import model_router as mr
from model_warehouse import catalog_merged

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]
PROMPT = "What is the weather in Beijing right now? Call the get_weather tool."
TIMEOUT = 25


def probe(base, key, model, provider):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 150,
        "temperature": 0,
        "stream": False,
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode())
        dt = round(time.time() - t0, 2)
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        tcs = msg.get("tool_calls") or []
        if tcs:
            return {"ok": True, "detail": "tool_calls", "ttfb_s": dt, "provider": provider}
        return {"ok": False, "detail": "no_tool_calls", "ttfb_s": dt, "provider": provider}
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:200]
        except Exception:
            detail = ""
        return {"ok": False, "detail": "HTTP%s %s" % (e.code, detail), "provider": provider}
    except Exception as e:
        return {"ok": False, "detail": "%s: %s" % (type(e).__name__, str(e)[:120]), "provider": provider}


def main():
    rows = []
    catalog = catalog_merged()
    picks = [c for c in catalog if c.get("role") == "vip_pick" and c.get("pick_enabled") is not False]
    layers = {"flash": "L1", "pro": "L2", "ultra": "L3", "auto": "L0", "shared": "QI"}
    results = {}

    for c in picks:
        pid = c["id"]
        or_id = (c.get("openrouter_id") or "").strip()
        chain = mr._vip_aggregator_chain(c, or_id)
        if not chain:
            results[pid] = {"status": "skip", "detail": "no chain", "modalities": c.get("modalities") or ["text"]}
            continue
        got = None
        for cand in chain:
            r = probe(cand["base"], cand["key"], cand["model"], cand["provider"])
            if r["ok"]:
                got = {"status": "ok", "channel": cand["provider"], "model": cand["model"], **r}
                break
            got = {"status": "fail", "channel": cand["provider"], "model": cand["model"], **r}
            if "400" in r["detail"] or "404" in r["detail"]:
                break  # model/tool not supported - don't waste failover
        got["modalities"] = c.get("modalities") or ["text"]
        results[pid] = got
        print("%-18s -> %s" % (pid, json.dumps({k: v for k, v in got.items() if k != "modalities"}, ensure_ascii=False)[:160]))
        rows.append({"id": pid, "title": c.get("title") or pid, **got})

    for label, layer in layers.items():
        up = mr._layer_upstream(layer)
        if not up.get("key") or not up.get("base"):
            results[label] = {"status": "skip", "detail": "no upstream", "modalities": ["text"]}
            print("%-18s -> skip (no upstream)" % label)
            continue
        r = probe(up["base"], up["key"], up.get("model") or up.get("or_model") or "", "layer-" + layer)
        results[label] = {"status": "ok" if r["ok"] else "fail", **r, "modalities": ["text"]}
        print("%-18s -> %s" % (label, json.dumps({k: v for k, v in results[label].items() if k != "modalities"}, ensure_ascii=False)[:160]))
        rows.append({"id": label, "title": label, **results[label]})

    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "models": rows}
    with open("..\\ops\\tools-support-20260813.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    ok = sum(1 for r in rows if r.get("status") == "ok")
    print("TOTAL=%d OK=%d FAIL=%d SKIP=%d" % (len(rows), ok, sum(1 for r in rows if r.get("status") == "fail"), sum(1 for r in rows if r.get("status") == "skip")))


if __name__ == "__main__":
    main()
