"""US market data providers (markets subproject).

主链: Tencent -> Eastmoney -> cache -> error.（Sina 已于 2026-08-16 移除：US K线接口不稳且熔断后报错泄漏到前端）
所有源统一返回 Candle rows: [date, open, close, high, low, vol]（与行情官口径一致）。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

_CACHE_DIR = Path(__file__).resolve().parent / ".." / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------- symbol mapping ----------
_TX_SYMBOL_MAP = {
    "^GSPC": "usINX",
    "^IXIC": "usIXIC",
    "^DJI": "usDJI",
    "^VIX": "usVIX",
}
_TX_INDEX_ALIASES = {
    "GSPC": "^GSPC",
    "SP500": "^GSPC",
    "SPX": "^GSPC",
    "IXIC": "^IXIC",
    "NASDAQ": "^IXIC",
    "DJI": "^DJI",
    "DOW": "^DJI",
    "DOWJONES": "^DJI",
}

# ---------- 名称 -> 代码（en/zh），搜索中文/英文名直接解析，避免把名称当代码去查 ----------
_NAME_TO_SYMBOL: Dict[str, str] = {}


def _reg_names(sym: str, *names: str) -> None:
    for n in names:
        if n:
            _NAME_TO_SYMBOL[n.lower().replace(".", "").replace(" ", "")] = sym


_reg_names("^DJI", "道琼斯", "道琼斯指数", "Dow Jones", "Dow")
_reg_names("^IXIC", "纳斯达克", "纳斯达克综合指数", "Nasdaq", "Nasdaq Composite")
_reg_names("^GSPC", "标普500", "标普", "标准普尔", "S&P 500", "S&P", "SP 500", "SP500")
_reg_names("^VIX", "恐慌指数", "VIX Index")
_reg_names("AAPL", "苹果", "苹果公司", "Apple")
_reg_names("NVDA", "英伟达", "辉达", "NVIDIA")
_reg_names("MSFT", "微软", "Microsoft")
_reg_names("GOOGL", "谷歌", "Alphabet", "Google")
_reg_names("AMZN", "亚马逊", "Amazon")
_reg_names("META", "Meta", "Meta Platforms", "Facebook", "脸书")
_reg_names("TSLA", "特斯拉", "Tesla")
_reg_names("NFLX", "奈飞", "网飞", "Netflix")
_reg_names("AMD", "超威半导体", "超微半导体")
_reg_names("INTC", "英特尔", "Intel")
_reg_names("TSM", "台积电", "TSMC", "Taiwan Semiconductor")
_reg_names("BABA", "阿里巴巴", "Alibaba")
_reg_names("PDD", "拼多多", "Pinduoduo")
_reg_names("JD", "京东", "JD.com", "Jingdong")
_reg_names("BIDU", "百度", "Baidu")
_reg_names("NTES", "网易", "NetEase")
_reg_names("NIO", "蔚来", "NIO")
_reg_names("LI", "理想汽车", "理想", "Li Auto")
_reg_names("XPEV", "小鹏汽车", "小鹏", "XPeng")
_reg_names("APLM", "冠科美博", "Apollomics", "冠科")
_reg_names("DIS", "迪士尼", "华特迪士尼", "Disney", "Walt Disney")
_reg_names("KO", "可口可乐", "Coca Cola", "Coca-Cola")
_reg_names("NKE", "耐克", "Nike")
_reg_names("BA", "波音", "Boeing")
_reg_names("GS", "高盛", "Goldman Sachs")
_reg_names("JPM", "摩根大通", "JPMorgan", "JP Morgan")
_reg_names("BAC", "美国银行", "Bank of America")
_reg_names("WFC", "富国银行", "Wells Fargo")
_reg_names("C", "花旗", "Citigroup", "Citi")
_reg_names("CSCO", "思科", "Cisco")
_reg_names("ORCL", "甲骨文", "Oracle")
_reg_names("CRM", "赛富时", "Salesforce")
_reg_names("UBER", "优步", "Uber")
_reg_names("ABNB", "爱彼迎", "Airbnb")
_reg_names("SBUX", "星巴克", "Starbucks")
_reg_names("MCD", "麦当劳", "McDonald's", "McDonalds")
_reg_names("WMT", "沃尔玛", "Walmart")
_reg_names("XOM", "埃克森美孚", "ExxonMobil", "Exxon")
_reg_names("CVX", "雪佛龙", "Chevron")
_reg_names("V", "Visa", "维萨")
_reg_names("MA", "Mastercard", "万事达")
_reg_names("PYPL", "PayPal", "贝宝")
_reg_names("SPY", "S&P 500 ETF", "标普500ETF", "标普500 ETF")
_reg_names("QQQ", "Nasdaq 100 ETF", "纳指100ETF", "纳指100 ETF", "纳斯达克100ETF")
_reg_names("DIA", "Dow Jones ETF", "道琼斯ETF")
_reg_names("IWM", "Russell 2000", "罗素2000")
_reg_names("TLT", "20+ Year Treasury", "长债ETF")
_reg_names("GLD", "Gold ETF", "黄金ETF")
_reg_names("VOO", "Vanguard S&P 500", "先锋标普500")
_reg_names("FXI", "China Large-Cap ETF", "中国大盘ETF")
_reg_names("KWEB", "中概互联", "China Internet ETF")
_reg_names("SOXX", "半导体ETF", "Semiconductor ETF")
_reg_names("XLK", "科技ETF", "Technology ETF")
_reg_names("XLF", "金融ETF", "Financial ETF")
_reg_names("XLE", "能源ETF", "Energy ETF")
# A股/港股指数（国际版也提供中国指数，腾讯 A 股接口直接可用，未开盘也能看历史日K）
_reg_names("sh000001", "上证指数", "上证", "Shanghai Composite", "SSE Composite", "SSE", "SHCOMP")
_reg_names("sh000016", "上证50", "上证50指数", "SSE 50")
_reg_names("sh000300", "沪深300", "沪深300指数", "CSI 300", "HS300")
_reg_names("sh000688", "科创50", "科创50指数", "STAR 50", "STAR50")
_reg_names("sh000905", "中证500", "中证500指数", "CSI 500")
_reg_names("sh000852", "中证1000", "中证1000指数", "CSI 1000")
_reg_names("sz399001", "深证成指", "深成指", "Shenzhen Component", "SZSE Component")
_reg_names("sz399006", "创业板指", "创业板", "ChiNext")
_reg_names("hkHSI", "恒生指数", "恒指", "Hang Seng", "HSI")

_CN_CODE_RE = re.compile(r"^(sh|sz|bj)\d{6}$")
_HK_CODE_RE = re.compile(r"^HK[A-Z0-9]+$")


def _cn_code(s: str) -> str:
    """识别中国代码（sh/sz/bj + 6 位数字 或 HK 前缀港股），返回腾讯小写形式；其它返回空串。"""
    low = (s or "").strip().lower()
    if _CN_CODE_RE.match(low):
        return low
    up = (s or "").strip().upper()
    if _HK_CODE_RE.match(up):
        return "hk" + up[2:]
    return ""


def resolve_symbol(symbol: str) -> str:
    """中文/英文名称归一化为代码；本身是代码或未知名称时原样返回。"""
    s = (symbol or "").strip()
    if not s:
        return symbol
    return _NAME_TO_SYMBOL.get(s.lower().replace(".", "").replace(" ", ""), symbol)


_EM_INDEX_MAP = {
    "usINX": "100.SPX",
    "usIXIC": "100.NDX",
    "usDJI": "100.DJI",
}
_EM_MARKET_PREFIXES = ("105.", "106.", "107.")

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
    return _client


def to_tencent_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError("empty symbol")
    cn = _cn_code(s)
    if cn:
        return cn
    if s in _TX_SYMBOL_MAP:
        return _TX_SYMBOL_MAP[s]
    if s.startswith("US") and len(s) > 2:
        return s
    return "us" + s


def _em_secids(symbol: str) -> List[str]:
    s = (symbol or "").strip().upper()
    cn = _cn_code(s)
    if cn:
        if cn.startswith("sh"):
            return ["1." + cn[2:]]  # 沪市指数 secid=1.xxxxxx
        if cn.startswith("sz"):
            return ["0." + cn[2:]]  # 深市指数 secid=0.xxxxxx
        return []  # 北证指数东财无此通道
    tx = to_tencent_symbol(s)
    if tx in _EM_INDEX_MAP:
        return [_EM_INDEX_MAP[tx]]
    bare = s[2:] if s.startswith("US") else s
    return [p + bare for p in _EM_MARKET_PREFIXES]


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        v = float(s)
        return v if v == v else None
    except Exception:
        return None


# ---------- rate gates & circuit breaker ----------
class _RateGate:
    def __init__(self, min_interval: float, per_minute: int):
        self.min_interval = min_interval
        self.per_minute = per_minute
        self._last = 0.0
        self._times: List[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self.min_interval - now
            cutoff = now - 60.0
            self._times = [t for t in self._times if t > cutoff]
            if len(self._times) >= self.per_minute and self._times:
                wait = max(wait, self._times[0] + 60.0 - now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self._times.append(self._last)


_TX_GATE = _RateGate(0.5, 120)
_EM_GATE = _RateGate(0.5, 90)
_CIRCUIT: Dict[str, Dict[str, Any]] = {}


def _circuit_open(source: str) -> bool:
    info = _CIRCUIT.get(source)
    return bool(info and info["open_until"] > time.time())


def _circuit_note(source: str, ok: bool) -> None:
    info = _CIRCUIT.setdefault(source, {"fail_count": 0, "open_until": 0.0})
    if ok:
        info["fail_count"] = 0
        info["open_until"] = 0.0
        return
    info["fail_count"] += 1
    if info["fail_count"] >= 3:
        info["open_until"] = time.time() + 150.0
        info["fail_count"] = 0


class _SourceError(RuntimeError):
    pass


class SymbolNotFoundError(_SourceError):
    def __init__(self, symbol: str, suggested: str = ""):
        self.symbol = symbol
        self.suggested = suggested
        msg = f"symbol not found: {symbol}"
        if suggested:
            msg += f"; did you mean {suggested}?"
        super().__init__(msg)


# 三源全部失败时区分“标的不存在”与“数据源故障”
_OUTAGE_MARKERS = (
    "timeout", "connect", "disconnected", "protocolerror", "status",
    "httpx", "ssl", "jsondecode", "reset by peer", "eof", "resolve", "errno",
)
_EMPTY_MARKERS = (
    "0 rows", "short (", "bad payload", "empty", "failed: none",
    "code matched", "missing", "index not supported",
)


def _looks_like_not_found(msg: str) -> bool:
    low = (msg or "").lower()
    if any(m in low for m in _OUTAGE_MARKERS):
        return False
    return any(m in low for m in _EMPTY_MARKERS)


def _suggest_candidates(symbol: str) -> List[str]:
    """生成候选代码：指数别名优先，其次尾字母裁剪（如 WETOUR → WETO）。"""
    raw = (symbol or "").strip().upper()
    bare = raw.replace("^", "")
    if bare.startswith("US") and len(bare) > 2:
        bare = bare[2:]
    out: List[str] = []
    if bare in _TX_INDEX_ALIASES:
        out.append(_TX_INDEX_ALIASES[bare])
    for cut in (1, 2, 3):
        if len(bare) > cut + 3:
            out.append(bare[:-cut])
    return out


async def _quiet_tencent_kline(symbol: str, count: int = 60) -> List[List[Any]]:
    """建议探测用：直接按候选代码拉腾讯K线，不计熔断、不查行情快照（避免熔断计数被连续探测打爆）。"""
    s = (symbol or "").strip().upper()
    tx = to_tencent_symbol(s)
    if tx in _TX_SYMBOL_MAP.values():
        codes = [tx]
    else:
        bare = s[2:] if s.startswith("US") and len(s) > 2 else s
        codes = [f"us{bare}{sfx}" for sfx in (".OQ", ".AM", ".N")]
    await _TX_GATE.acquire()
    client = _get_client()
    for code in dict.fromkeys(codes):
        try:
            url = f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},day,,,{count},qfq"
            r = await client.get(url)
            r.raise_for_status()
            payload = r.json()
            node = (payload.get("data") or {}).get(code) or {}
            rows = node.get("day") or node.get("qfqday") or []
            if rows:
                return rows
        except Exception:
            continue
    return []


async def _suggest_symbol(symbol: str) -> str:
    """标的找不到时静默试候选代码，命中返回建议代码，否则空串。"""
    for cand in _suggest_candidates(symbol):
        try:
            rows = await _quiet_tencent_kline(cand, 60)
            if rows:
                return cand
        except Exception:
            continue
    return ""


# ---------- Tencent (primary) ----------
async def fetch_tencent_kline(symbol: str, count: int = 500) -> Tuple[List[List[Any]], List[str]]:
    """Return (rows, qt_fields). rows: [date, open, close, high, low, vol]."""
    tx = to_tencent_symbol(symbol)
    if _circuit_open("tencent"):
        raise _SourceError("tencent circuit open")

    cn = _cn_code(tx)
    # A股指数/代码走腾讯 A 股接口（未开盘也返回完整历史日K，无当日残缺 bar）
    if cn:
        codes = [cn]
    elif tx in _TX_SYMBOL_MAP.values():
        # 指数直接带 us 前缀即可（usINX/usIXIC/usDJI/usVIX）
        codes = [tx]
    else:
        # 个股/ETF 必须带市场后缀：AAPL.OQ / SPY.AM / BRK.A.N
        # 优先从行情快照取市场限定代码（field[2]），失败则按候选后缀逐个试
        codes: List[str] = []
        try:
            quote = await fetch_tencent_quote(symbol)
            mkt = quote.get("market_code") or ""
            if mkt:
                codes.append("us" + mkt)
        except Exception:
            pass
        bare = symbol.upper()
        if bare.startswith("US"):
            bare = bare[2:]
        codes += [f"us{bare}{s}" for s in (".OQ", ".AM", ".N")]

    last_err: Optional[Exception] = None
    await _TX_GATE.acquire()
    try:
        client = _get_client()
        for code in dict.fromkeys(codes):
            try:
                if _cn_code(code):
                    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{count},qfq"
                else:
                    url = f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},day,,,{count},qfq"
                r = await client.get(url)
                r.raise_for_status()
                payload = r.json()
                node = (payload.get("data") or {}).get(code) or {}
                rows = node.get("day") or node.get("qfqday") or []
                qt = (node.get("qt") or {}).get(code) or []
                if len(rows) >= min(30, count):
                    _circuit_note("tencent", True)
                    return rows, qt
                last_err = _SourceError(f"tencent kline short ({len(rows)} rows) for {code}")
            except Exception as e:
                last_err = e
                continue
        raise last_err or _SourceError("no tencent kline code matched")
    except Exception as e:
        _circuit_note("tencent", False)
        raise _SourceError(f"tencent kline failed: {e}") from e


async def fetch_tencent_quote(symbol: str) -> Dict[str, Any]:
    tx = to_tencent_symbol(symbol)
    await _TX_GATE.acquire()
    try:
        client = _get_client()
        cn = _cn_code(tx)
        url = f"https://qt.gtimg.cn/q={tx}"
        r = await client.get(url)
        r.raise_for_status()
        text = r.content.decode("gbk", errors="replace") if cn else r.text
        key = f'v_{tx}="'
        start = text.find(key)
        if start < 0:
            raise _SourceError("tencent quote missing")
        end = text.find('"', start + len(key))
        fields = text[start + len(key):end].split("~")
        if len(fields) < 40:
            raise _SourceError("tencent quote short")
        _circuit_note("tencent", True)
        if cn:
            return {
                "symbol": symbol.upper(),
                "name": fields[1] if len(fields) > 1 else symbol.upper(),
                "market_code": cn,
                "price": _f(fields[3]),
                "prev_close": _f(fields[4]),
                "open": _f(fields[5]),
                "high": _f(fields[33]) if len(fields) > 33 else None,
                "low": _f(fields[34]) if len(fields) > 34 else None,
                "change": _f(fields[31]) if len(fields) > 31 else None,
                "pct": _f(fields[32]) if len(fields) > 32 else None,
                "volume": _f(fields[6]),
                "amount": _f(fields[37]) if len(fields) > 37 else None,
                "time": fields[30] if len(fields) > 30 else "",
                "currency": "HKD" if cn.startswith("hk") else "CNY",
                "pe": _f(fields[39]) if len(fields) > 39 else None,
                "source": "tencent",
            }
        name_en = fields[46] if len(fields) > 46 else ""
        return {
            "symbol": symbol.upper(),
            "name": name_en or fields[2],
            "market_code": fields[2] if len(fields) > 2 else "",
            "price": _f(fields[3]),
            "prev_close": _f(fields[4]),
            "open": _f(fields[5]),
            "high": _f(fields[33]) if len(fields) > 33 else None,
            "low": _f(fields[34]) if len(fields) > 34 else None,
            "change": _f(fields[31]) if len(fields) > 31 else None,
            "pct": _f(fields[32]) if len(fields) > 32 else None,
            "volume": _f(fields[6]),
            "amount": _f(fields[37]) if len(fields) > 37 else None,
            "time": fields[30] if len(fields) > 30 else "",
            "currency": fields[35] if len(fields) > 35 else "USD",
            "pe": _f(fields[39]) if len(fields) > 39 else None,
            "source": "tencent",
        }
    except Exception as e:
        _circuit_note("tencent", False)
        raise _SourceError(f"tencent quote failed: {e}") from e


# ---------- Eastmoney (fallback 1) ----------
def _drop_auction_today_bar(rows: List[List[Any]]) -> List[List[Any]]:
    """集合竞价/开盘前剔除东财当日残缺 bar（与 a1 providers._drop_auction_today_bar 同口径）。

    push2his 在 09:15-09:25 竞价与 09:25-09:30 过渡期会返回未成形当日 K：
    high/low 常为 0 或撮合价剧烈跳动，画出来像“大阴柱”，MACD 量能柱也被拉成极端负值。
    - 交易日 09:30 前：当日 bar 无意义，直接剔除；
    - 09:30 后：保留，但 OHLC 任一非法（<=0）仍剔除。
    """
    try:
        now = datetime.now()
        if now.weekday() >= 5:
            return rows
        today = now.date().isoformat()
        hhmm = now.strftime("%H%M")
        out: List[List[Any]] = []
        for r in rows:
            if not (isinstance(r, (list, tuple)) and len(r) >= 5) or str(r[0]) != today:
                out.append(r)
                continue
            if hhmm < "093000":
                continue
            try:
                o, c, h, l = float(r[1]), float(r[2]), float(r[3]), float(r[4])
            except Exception:
                continue
            if min(o, c, h, l) <= 0:
                continue
            out.append(r)
        return out
    except Exception:
        return rows


async def fetch_em_kline(symbol: str, count: int = 500) -> List[List[Any]]:
    if _circuit_open("eastmoney"):
        raise _SourceError("eastmoney circuit open")
    secids = _em_secids(symbol)
    last_err: Optional[Exception] = None
    await _EM_GATE.acquire()
    try:
        client = _get_client()
        for sid in secids:
            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={sid}&klt=101&fqt=1"
                f"&lmt={count}&end=20500101&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
            )
            try:
                r = await client.get(url)
                r.raise_for_status()
                data = (r.json() or {}).get("data") or {}
                klines = data.get("klines") or []
                rows: List[List[Any]] = []
                for line in klines:
                    parts = str(line).split(",")
                    if len(parts) >= 6:
                        rows.append([parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]])
                if rows:
                    _circuit_note("eastmoney", True)
                    return _drop_auction_today_bar(rows)
            except Exception as e:
                last_err = e
                continue
    finally:
        pass
    _circuit_note("eastmoney", False)
    raise _SourceError(f"eastmoney kline failed: {last_err}")


# ---------- cache & orchestration ----------
def _today_str() -> str:
    return date.today().isoformat()


def _cache_file(kind: str, symbol: str, period: str) -> Path:
    tx = to_tencent_symbol(symbol).replace("^", "")
    return _CACHE_DIR / f"{kind}_{tx}_{period}.json"


def _is_bad_intraday_bar(row: List[Any]) -> bool:
    """当日 bar 是否为占位/异常：竞价或未开盘时腾讯可能返回全 0 / 缺字段，
    渲染会画出假的大阴线（K线 + MACD 同现）。"""
    try:
        if not row or len(row) < 6:
            return True
        o, c, h, l, v = (float(row[i]) for i in range(1, 6))
        if o <= 0 or c <= 0 or h <= 0 or l <= 0 or v <= 0:
            return True
        if h < l or c > h or c < l or o > h or o < l:
            return True
        return False
    except Exception:
        return True


def _drop_bad_intraday_bar(rows: List[List[Any]], today: str) -> List[List[Any]]:
    """剔除最后一根当日异常 bar（竞价占位），保留完整历史。"""
    if not rows:
        return rows
    last = rows[-1]
    if str(last[0]) == today and _is_bad_intraday_bar(last):
        return rows[:-1]
    return rows


def _cn_cache_valid(obj: Dict[str, Any], rows: List[List[Any]]) -> bool:
    """中国代码当日缓存有效期：无当日 bar → 300s（开盘后补当日）；
    当日有效 bar → 60s（盘中刷新可见最新）；当日异常 bar → 30s（尽快剔除占位）。"""
    now = time.time()
    ts = float(obj.get("ts", 0) or 0)
    if not rows:
        return now - ts < 30
    last = rows[-1]
    if str(last[0]) == _today_str():
        if _is_bad_intraday_bar(last):
            return now - ts < 30
        return now - ts < 60
    return now - ts < 300


async def get_kline_rows(symbol: str, period: str = "day", count: int = 500) -> Dict[str, Any]:
    period = period or "day"
    symbol = resolve_symbol(symbol)
    cache = _cache_file("kline", symbol, period)
    cn = bool(_cn_code(symbol))
    if cache.exists():
        try:
            obj = json.loads(cache.read_text(encoding="utf-8"))
            rows = obj.get("rows", [])
            # 命中条件：根数足够，或该缓存已标记“上游历史已取完”（短历史标的避免反复重拉）。
            # 不能用 min(count,30) 兜底：250 根时代的旧缓存会污染 count=500 请求（04 验收实测踩坑）。
            ok = (
                obj.get("day") == _today_str()
                and (len(rows) >= count or obj.get("complete"))
            )
            if cn:
                ok = ok and _cn_cache_valid(obj, rows)
            if ok:
                return obj
        except Exception:
            pass

    fetch_n = max(count, 500)
    rows: List[List[Any]] = []
    source = ""
    try:
        rows, _qt = await fetch_tencent_kline(symbol, fetch_n)
        source = "tencent"
    except Exception as e1:
        try:
            rows = await fetch_em_kline(symbol, fetch_n)
            source = "eastmoney"
        except Exception as e2:
            if cache.exists():
                try:
                    obj = json.loads(cache.read_text(encoding="utf-8"))
                    if obj.get("rows"):
                        obj["source"] = "cache"
                        return obj
                except Exception:
                    pass
            # 任一源给出“标的不存在”信号（如 0 rows/empty）即视为未找到，静默探测建议代码；
            # 仅当所有失败都是断连/超时/熔断等故障信号时才报“no data available”。
            if _looks_like_not_found(str(e1)) or _looks_like_not_found(str(e2)):
                suggested = await _suggest_symbol(symbol)
                raise SymbolNotFoundError(symbol, suggested) from e2
            # 两源都在故障/熔断：静默探测候选（_quiet_tencent_kline 绕过熔断不计失败）。
            # 候选命中说明用户拼错了代码（如 WETOUR→WETO），应给建议而不是笼统报“无数据”；
            # 候选全空（真代码在总故障期）仍报“no data available”，不误判为不存在。
            suggested = await _suggest_symbol(symbol)
            if suggested:
                raise SymbolNotFoundError(symbol, suggested) from e2
            raise _SourceError(f"no data available for {symbol}") from e2

    if not rows:
        raise _SourceError(f"no data for {symbol}")
    if cn:
        rows = _drop_bad_intraday_bar(rows, _today_str())
    obj = {
        "symbol": symbol,
        "period": period,
        "day": _today_str(),
        "rows": rows,
        "source": source,
        "complete": len(rows) < fetch_n,  # 上游已无更多历史
        "ts": time.time(),
    }
    try:
        cache.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return obj


async def get_quote(symbol: str) -> Dict[str, Any]:
    symbol = resolve_symbol(symbol)
    cache = _cache_file("quote", symbol, "rt")
    if cache.exists():
        try:
            obj = json.loads(cache.read_text(encoding="utf-8"))
            price = obj.get("price")
            if time.time() - obj.get("ts", 0) < 30 and price and price > 0:
                return obj
        except Exception:
            pass
    try:
        quote = await fetch_tencent_quote(symbol)
    except Exception as e:
        if _looks_like_not_found(str(e)):
            suggested = await _suggest_symbol(symbol)
            raise SymbolNotFoundError(symbol, suggested) from e
        raise
    price = quote.get("price")
    if price is None or price <= 0:
        suggested = await _suggest_symbol(symbol)
        raise SymbolNotFoundError(symbol, suggested)
    quote["ts"] = time.time()
    try:
        cache.write_text(json.dumps(quote, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return quote
