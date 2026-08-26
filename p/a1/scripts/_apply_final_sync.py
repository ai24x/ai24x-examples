# -*- coding: utf-8 -*-
"""03 侧应用「本地最终版」复盘/掘金归档同步包（本地为权威，老板验收口径）。

用法: python _apply_final_sync.py <pkg_dir>
包结构（pkg_dir）:
  bj_archive/*.json              掘金历史归档（含 archive_index / winrate_cache）
  bj_scan_history.json           掘金扫描历史索引（每日最终版）
  bj_scan_daily.json             掘金当日扫描缓存（合并，本地优先）
  bj_emotion/*.json              情绪周期快照/涨停池
  daily_report_config.json       daily_report config（15:10 收盘定型口径）
  daily_report_cache/<YYYYMMDD>/ 复盘按日上游缓存
  mainlines_archive/<YYYYMMDD>/  复盘归档（板块主攻研判：mainlines/observes 权威来源）

执行：备份 C:\\backup\\ai24x_a\\ → 覆盖/合并 → 重建归档索引 → 打印验证。
"""
import glob
import io
import json
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PKG = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\_a1_final_sync"
A1 = r"C:\ai24x01\p\a1"
DATA = os.path.join(A1, "api", "server", "data")
ARCH = os.path.join(DATA, "bj_archive")
EMO = os.path.join(DATA, "bj_emotion")
DR = os.path.join(A1, "daily_report")
ML_ROOT = os.path.join(A1, "调研报告", "04-每日跟踪", "板块主攻研判")
BK = os.path.join(r"C:\backup\ai24x_a", "gd_final_sync_" + time.strftime("%Y%m%d_%H%M%S"))


def _backup():
    os.makedirs(BK, exist_ok=True)
    for tag, d in (("bj_archive", ARCH), ("bj_emotion", EMO), ("daily_report_cache", os.path.join(DR, "cache")), ("mainlines_archive", ML_ROOT)):
        if os.path.isdir(d):
            shutil.copytree(d, os.path.join(BK, tag), dirs_exist_ok=True)
    for fn in ("bj_scan_history.json", "bj_scan_daily.json", "config.json"):
        p = os.path.join(DATA if fn != "config.json" else DR, fn)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(BK, fn))
    print("BACKUP=" + BK)


def _merge_json(src, dst, cap=None):
    """合并 JSON：本地（包内）优先，保留目标独有键；cap 限长（FIFO 淘汰最旧）。"""
    if not os.path.exists(src):
        return 0
    cur = {}
    if os.path.exists(dst):
        try:
            cur = json.load(open(dst, encoding="utf-8"))
        except Exception:
            cur = {}
    new = json.load(open(src, encoding="utf-8"))
    n = 0
    for k, v in new.items():
        cur[k] = v
        n += 1
    if cap and len(cur) > cap:
        for k in list(cur.keys())[: len(cur) - cap]:
            cur.pop(k, None)
    json.dump(cur, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    return n


def main():
    _backup()
    # 1) 掘金历史归档（本地最终版覆盖）
    n = 0
    for fn in glob.glob(os.path.join(PKG, "bj_archive", "*.json")):
        shutil.copy2(fn, os.path.join(ARCH, os.path.basename(fn)))
        n += 1
    print("ARCHIVE_COPIED=" + str(n))
    # 2) 扫描历史/当日缓存（合并，本地优先）
    print("HIST_MERGED=" + str(_merge_json(os.path.join(PKG, "bj_scan_history.json"), os.path.join(DATA, "bj_scan_history.json"), cap=12)))
    print("DAILY_MERGED=" + str(_merge_json(os.path.join(PKG, "bj_scan_daily.json"), os.path.join(DATA, "bj_scan_daily.json"))))
    # 3) 情绪快照
    n = 0
    for fn in glob.glob(os.path.join(PKG, "bj_emotion", "*.json")):
        shutil.copy2(fn, os.path.join(EMO, os.path.basename(fn)))
        n += 1
    print("EMOTION_COPIED=" + str(n))
    # 4) daily_report config（15:10）
    cfg = os.path.join(PKG, "daily_report_config.json")
    if os.path.exists(cfg):
        shutil.copy2(cfg, os.path.join(DR, "config.json"))
        print("CFG=15:10" if "15:10" in open(cfg, encoding="utf-8").read() else "CFG?")
    # 5) daily_report 按日缓存
    n = 0
    for d in glob.glob(os.path.join(PKG, "daily_report_cache", "*")):
        if os.path.isdir(d):
            shutil.copytree(d, os.path.join(DR, "cache", os.path.basename(d)), dirs_exist_ok=True)
            n += 1
    print("DR_CACHE_DIRS=" + str(n))
    # 6) 复盘归档（板块主攻研判：主线/观察板块权威）
    n = 0
    for d in glob.glob(os.path.join(PKG, "mainlines_archive", "*")):
        if os.path.isdir(d):
            shutil.copytree(d, os.path.join(ML_ROOT, os.path.basename(d)), dirs_exist_ok=True)
            n += 1
    print("ML_ARCHIVE_DIRS=" + str(n))
    # 7) 重建归档索引
    sys.path.insert(0, os.path.join(A1, "api", "server"))
    from app.bj_screener import _rebuild_archive_index
    _rebuild_archive_index()
    print("INDEX_REBUILT")
    # 8) 验证
    ml = os.path.join(ML_ROOT, "20260825", "mainlines.json")
    if os.path.exists(ml):
        print("ML20260825=" + open(ml, encoding="utf-8").read().replace("\n", " ").strip())
    h = json.load(open(os.path.join(DATA, "bj_scan_history.json"), encoding="utf-8"))
    hs = h.get("hs:2026-08-25") or {}
    picks = hs.get("picks") or []
    print("HS25_PICKS=" + json.dumps([p.get("name") for p in picks[:4]], ensure_ascii=False))
    # 9) picks 与本地包一致（当日）
    today8 = time.strftime("%Y%m%d")
    verify = os.path.join(PKG, "_verify_final_sync.py")
    if os.path.exists(verify):
        import subprocess
        r = subprocess.run([sys.executable, verify, PKG, today8], capture_output=True, text=True, encoding="utf-8")
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip())
            raise SystemExit("VERIFY_FAIL")
    print("DONE")


if __name__ == "__main__":
    main()
