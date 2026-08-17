"""2026-08-17 集合竞价 K 线修复单元测试（无网络依赖）。

验证 providers_us 的竞价剔除逻辑：
1. _drop_auction_today_bar：09:30 前剔除当日残缺 bar；09:30 后仅剔除非法 OHLC。
2. _drop_bad_intraday_bar / _is_bad_intraday_bar：占位 bar 剔除、正常 bar 保留。
3. _cn_cache_valid：无当日 bar -> 300s；当日有效 -> 60s；当日异常 -> 30s。
"""
import importlib.util
import sys
from unittest import mock

MOD_PATH = r"E:\AI24X\ai24x-website\ai24x01\p\markets\api\server\app\providers_us.py"

spec = importlib.util.spec_from_file_location("providers_us_test", MOD_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

fails = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        fails.append(name)


# ---- 1. _drop_auction_today_bar ----
rows = [
    ["2026-08-14", "3927.18", "3927.18", "3932.64", "3903.70", "499525613.0"],
    ["2026-08-17", "0", "3960.19", "3961.82", "3924.47", "310788423.0"],  # 竞价占位: open=0
    ["2026-08-17", "3930.10", "0", "3961.82", "3924.47", "310788423.0"],  # close=0
    ["2026-08-17", "3930.10", "3960.19", "3961.82", "3924.47", "310788423.0"],  # 合法
]


def fake_dt(iso):
    class _FakeDT:
        @classmethod
        def now(cls, tz=None):
            from datetime import datetime
            return datetime.strptime(iso, "%Y-%m-%d %H:%M:%S")
    return _FakeDT


with mock.patch.object(mod, "datetime", fake_dt("2026-08-17 09:20:00")):
    out = mod._drop_auction_today_bar(list(rows))
    check("auction 09:20 drops all today rows", all(str(r[0]) != "2026-08-17" for r in out))
    check("auction 09:20 keeps history rows", len(out) == 1)


with mock.patch.object(mod, "datetime", fake_dt("2026-08-17 14:30:00")):
    out = mod._drop_auction_today_bar(list(rows))
    check("intraday keeps valid today row", any(str(r[0]) == "2026-08-17" and float(r[1]) > 0 for r in out))
    check("intraday drops invalid today rows", all(
        not (str(r[0]) == "2026-08-17" and (float(r[1]) <= 0 or float(r[2]) <= 0)) for r in out))

# ---- 2. _is_bad_intraday_bar / _drop_bad_intraday_bar ----
bad_zero = ["2026-08-17", "0", "3960.19", "3961.82", "3924.47", "310788423.0"]
bad_hl = ["2026-08-17", "3930.10", "3960.19", "3924.47", "3961.82", "310788423.0"]  # high < low
good = ["2026-08-17", "3930.10", "3960.19", "3961.82", "3924.47", "310788423.0"]
check("bad bar: zero open", mod._is_bad_intraday_bar(bad_zero))
check("bad bar: high<low", mod._is_bad_intraday_bar(bad_hl))
check("good bar: valid", not mod._is_bad_intraday_bar(good))
check("drop bad last bar", mod._drop_bad_intraday_bar([good, bad_zero], "2026-08-17") == [good])
check("keep good last bar", mod._drop_bad_intraday_bar([good], "2026-08-17") == [good])

# ---- 3. _cn_cache_valid ----
now = mod.time.time()
check("no today row -> 300s window", mod._cn_cache_valid({"ts": now}, [["2026-08-14", "1", "2", "3", "0.5", "1"]]) is True)
check("no today row -> stale after 300s", mod._cn_cache_valid({"ts": now - 301}, [["2026-08-14", "1", "2", "3", "0.5", "1"]]) is False)
check("valid today row -> 60s window", mod._cn_cache_valid({"ts": now}, [[ "2026-08-17", "1", "2", "3", "0.5", "1"]]) is True)
check("valid today row -> stale after 60s", mod._cn_cache_valid({"ts": now - 61}, [["2026-08-17", "1", "2", "3", "0.5", "1"]]) is False)
check("bad today row -> 30s window", mod._cn_cache_valid({"ts": now}, [[ "2026-08-17", "0", "2", "3", "0.5", "1"]]) is True)
check("bad today row -> stale after 30s", mod._cn_cache_valid({"ts": now - 31}, [["2026-08-17", "0", "2", "3", "0.5", "1"]]) is False)

print()
if fails:
    print("FAILED:", fails)
    sys.exit(1)
print("ALL PASS")
