# -*- coding: utf-8 -*-
"""生成 BK<->THS 板块映射表（东财板块代码 / 同花顺指数代码）"""
import asyncio, json, os, re, sys, time
SRV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "server")
sys.path.insert(0, SRV)
import httpx
from app.ths_fuyao import fuyao_config

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}

def norm(name):
    if not name: return ""
    s = str(name).strip().lower()
    s = re.sub(r"[\s_\-（）()]+", "", s)
    s = re.sub(r"[（(].*?[)）]", "", s)          # 去括号内容
    s = re.sub(r"(?:ii+|iii+|iv+|v|vi+|vii+)$", "", s)  # 去罗马数字后缀 证券II/证券III
    s = s.replace("指数", "").replace("板块", "").replace("概念", "").replace("行业", "")
    return s

async def fetch_ths_catalog():
    cfg = fuyao_config()
    key = str(cfg.get("api_key") or "")
    base = str(cfg.get("base_url") or "").rstrip("/") or "https://fuyao.aicubes.cn"
    headers = {"X-api-key": key, "User-Agent": "ai24x/1.0"}
    out = []
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as c:
        for tag in ("industry", "cn_concept"):
            r = await c.get(base + "/api/a-share-index/catalog/ths-index-list", params={"tag": tag})
            data = r.json()
            items = (data.get("data") or {}).get("item") or []
            for it in items:
                out.append({"thscode": str(it.get("thscode") or ""), "name": str(it.get("name") or ""), "tag": tag})
            print(f"ths {tag}: {len(items)}")
    return out

async def fetch_em_plates():
    out = []
    url = "https://push2delay.eastmoney.com/api/qt/clist/get"
    async with httpx.AsyncClient(timeout=20.0, headers=UA) as c:
        for t in ("2", "3"):
            pn = 1
            while pn <= 20:
                params = {"pn": pn, "pz": 100, "po": 1, "np": 1, "fltt": 2, "invt": 2,
                          "fid": "f3", "fs": f"m:90+t:{t}", "fields": "f12,f14"}
                r = await c.get(url, params=params)
                data = r.json()
                diff = (data.get("data") or {}).get("diff") or []
                items = list(diff.values()) if isinstance(diff, dict) else list(diff)
                for it in items:
                    out.append({"bk": str(it.get("f12") or ""), "name": str(it.get("f14") or ""), "type": t})
                total = int((data.get("data") or {}).get("total") or 0)
                if not items or pn * 100 >= total:
                    print(f"em t:{t} pn={pn} total={total} got={len([x for x in out if x['type']==t])}")
                    break
                pn += 1
                await asyncio.sleep(0.3)
    return out

async def main():
    ths = await fetch_ths_catalog()
    em = await fetch_em_plates()
    em_by_norm = {}
    for e in em:
        n = norm(e["name"])
        if n and (n not in em_by_norm or len(e["bk"]) < len(em_by_norm[n]["bk"])):
            em_by_norm[n] = e
    ths_by_norm = {}
    for t in ths:
        n = norm(t["name"])
        if n and n not in ths_by_norm:
            ths_by_norm[n] = t
    MANUAL = [
        # 东财BK    ths代码        ths显示名          tag
        ("BK1128", "886033.TI", "共封装光学(CPO)", "cn_concept"),
        ("BK1134", "886050.TI", "算力租赁", "cn_concept"),
        ("BK1064", "885957.TI", "东数西算(算力)", "cn_concept"),
        ("BK0473", "881157.TI", "证券", "industry"),
        ("BK0928", "885959.TI", "PCB概念", "cn_concept"),
        ("BK0616", "885872.TI", "光模块", "cn_concept"),
        ("BK1037", "881124.TI", "消费电子", "industry"),
        ("BK0450", "881157.TI", "证券", "industry"),
    ]
    pairs, unmatched = [], []
    matched_norm = set()
    # pass1: 精确
    for n, t in ths_by_norm.items():
        e = em_by_norm.get(n)
        if e:
            pairs.append({"bk": e["bk"], "ths": t["thscode"], "name": t["name"], "tag": t["tag"]})
            matched_norm.add(n)
    # pass2: 包含（ths 名包含 em 名，双向取短名）
    for n, t in ths_by_norm.items():
        if n in matched_norm: continue
        cand = []
        for en, e in em_by_norm.items():
            if len(en) < 2: continue
            if en in n or n in en:
                cand.append(e)
        if cand:
            cand.sort(key=lambda x: len(norm(x["name"])))
            e = cand[0]
            pairs.append({"bk": e["bk"], "ths": t["thscode"], "name": t["name"], "tag": t["tag"]})
            matched_norm.add(n)
    # pass3: 人工校正表（强制覆盖该 BK 的映射）
    for bk, ths_code, name, tag in MANUAL:
        pairs = [x for x in pairs if x["bk"] != bk]
        pairs.append({"bk": bk, "ths": ths_code, "name": name, "tag": tag})
    seen = set()
    dedup = []
    for x in pairs:
        k = (x["bk"], x["ths"])
        if k not in seen:
            seen.add(k); dedup.append(x)
    pairs = dedup
    for n, t in ths_by_norm.items():
        if n not in matched_norm:
            unmatched.append({"ths": t["thscode"], "name": t["name"], "tag": t["tag"]})
    # 反向：东财有但ths没有的
    em_unmatched = []
    for n, e in em_by_norm.items():
        if n not in ths_by_norm:
            em_unmatched.append({"bk": e["bk"], "name": e["name"], "type": e["type"]})
    pairs.sort(key=lambda x: x["ths"])
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "pairs": pairs,
           "ths_unmatched": unmatched, "em_unmatched": em_unmatched}
    path = os.path.join(SRV, "data", "plate_map_bk_ths.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"pairs={len(pairs)} ths_unmatched={len(unmatched)} em_unmatched={len(em_unmatched)}")
    print("saved", path)
    for p in pairs[:25]:
        print(f"  {p['bk']} <-> {p['ths']}  {p['name']}")

asyncio.run(main())
