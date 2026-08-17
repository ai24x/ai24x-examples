import json, os, urllib.request, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
cache = Path("_tmp_mc.json")
cm = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}

def fetch(name, base, key):
    if name in cm and cm[name]:
        return cm[name]
    req = urllib.request.Request(base + "/models", headers={"Authorization": f"Bearer {key}"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    ids = [m.get("id","") for m in data.get("data", [])]
    print(f"{name}: {len(ids)} models in {time.time()-t0:.0f}s")
    cm[name] = ids
    cache.write_text(json.dumps(cm), encoding="utf-8")
    return ids

tl = fetch("tokenlab", "https://api.tokenlab.sh/v1", os.environ["TOKENLAB_API_KEY"])
or_ = fetch("openrouter", "https://openrouter.ai/api/v1", os.environ["OPENROUTER_API_KEY"])
rq = fetch("requesty", "https://router.requesty.ai/v1", os.environ["REQUESTY_API_KEY"])

print("\n=== Grok ===")
for w in ("grok-4.20", "x-ai/grok", "grok-4"):
    for name, ids in (("TL", tl), ("OR", or_), ("RQ", rq)):
        hits = [i for i in ids if w.lower() in i.lower()]
        if hits: print(f"{name} [{w}]: {hits[:6]}")
print("=== Llama ===")
for w in ("llama-4", "meta-llama/llama", "llama-5"):
    for name, ids in (("TL", tl), ("OR", or_), ("RQ", rq)):
        hits = [i for i in ids if w.lower() in i.lower()]
        if hits: print(f"{name} [{w}]: {hits[:6]}")
print("=== 旗舰确认 ===")
for w in ("gpt-5.4", "claude-sonnet-5", "claude-opus-5", "gemini-3.6-flash"):
    for name, ids in (("TL", tl), ("OR", or_), ("RQ", rq)):
        hits = [i for i in ids if w.lower() in i.lower() and not i.startswith("openai-responses")]
        if hits: print(f"{name} [{w}]: {hits[:4]}")
