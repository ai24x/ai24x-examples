# -*- coding: utf-8 -*-
"""
自选股技术面评分（P1）。

口径：综合分 0-100，仅为技术规则量化结果，不构成投资建议。
因子权重（基础）：MACD量能柱 25 / 均线底部金叉 20 / 量能确认 15 / 异动回踩 15 / 位置安全边际 10 / 趋势环境 10，基准 +5。
核心增强因子（叠加、可正可负，综合分封顶 100）：RSI 动能位置 / 量价配合度 / 波动蓄势与放量突破 / 大盘环境（上证指数 MACD 红柱天数 + 均线信号，由接口层并入）。
风险提示：ST/退市、连续下杀、多次跌停、破位下行、高位滞涨、量能低迷、放量杀跌、长上影滞涨、涨停开板、创60日新低、跌破双均线、5日涨幅过大、放量过热、量价背离、波动骤增。
"""
from __future__ import annotations

from typing import Any

from .signals import Candle, _compute_macd_arrays


def _ma(closes: list[float], n: int) -> list[float]:
    out: list[float] = []
    s = 0.0
    for i, c in enumerate(closes):
        s += c
        if i >= n:
            s -= closes[i - n]
        out.append(s / n if i >= n - 1 else float("nan"))
    return out


def _slope_ratio(vals: list[float], back: int = 5) -> float:
    if len(vals) < back + 2:
        return 0.0
    cur = vals[-1]
    ref = vals[-1 - back]
    if cur != cur or ref != ref or abs(ref) < 1e-9:
        return 0.0
    return (cur - ref) / abs(ref)


def _red_days(bar: list[float]) -> int:
    n = 0
    for v in reversed(bar):
        if v > 0:
            n += 1
        else:
            break
    return n


def _rsi(closes: list[float], period: int = 14) -> float:
    """简单 RSI(14)：用最近 period 个涨跌幅的均值增益/均值损失。"""
    if len(closes) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        chg = closes[i] - closes[i - 1]
        if chg >= 0:
            gains += chg
        else:
            losses -= chg
    if losses == 0.0:
        return 100.0 if gains > 0 else 50.0
    rs = gains / losses
    return 100.0 - 100.0 / (1.0 + rs)


def _avg_range_pct(highs: list[float], lows: list[float], closes: list[float], back: int) -> float:
    """最近 back 个交易日的平均日内振幅（(高-低)/收）。"""
    n = len(closes)
    start = max(1, n - back)
    if n - start <= 0:
        return 0.0
    total = 0.0
    cnt = 0
    for i in range(start, n):
        if closes[i] > 0:
            total += (highs[i] - lows[i]) / closes[i]
            cnt += 1
    return total / cnt if cnt else 0.0


def score_candles(candles: list[Candle], *, name: str = "") -> dict[str, Any]:
    """输入日线 Candle（>=60 根），输出评分结果 dict。"""
    if not candles or len(candles) < 60:
        return {"ok": False, "msg": "need >=60 candles", "score": 0}
    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    vols = [float(c.vol or 0.0) for c in candles]
    n = len(closes)

    dif, dea, bar, golden, dead = _compute_macd_arrays(closes)
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    ma57 = _ma(closes, 57)
    ma60 = _ma(closes, 60)
    ma144 = _ma(closes, 144) if n >= 144 else None

    cur = closes[-1]
    prev = closes[-2]
    cur_vol = vols[-1]
    avg20_vol = (sum(vols[-21:-1]) / 20.0) if n >= 21 else (sum(vols) / max(1, n))
    avg5_vol = (sum(vols[-5:]) / 5.0) if n >= 5 else cur_vol
    vol_ratio = cur_vol / avg20_vol if avg20_vol > 0 else 0.0
    up_pct = (cur / prev - 1.0) * 100.0 if prev > 0 else 0.0

    factors: dict[str, float] = {}
    tags: list[str] = []
    risks: list[str] = []

    # ---- MACD 量能柱 (25) ----
    rd = _red_days(bar)
    macd_pts = 0.0
    if rd >= 1:
        if rd == 1:
            macd_pts = 22.0
        elif rd == 2:
            macd_pts = 19.0
        elif rd == 3:
            macd_pts = 16.0
        elif rd <= 6:
            macd_pts = 12.0
        else:
            macd_pts = 8.0
        if bar[-1] > bar[-2]:
            macd_pts += 3.0
        if dif[-1] > dea[-1]:
            macd_pts += 2.0
        macd_pts = min(25.0, macd_pts)
        tags.append("MACD翻红·第%d天" % rd)
        if bar[-1] > bar[-2]:
            tags.append("红柱放大")
    factors["macd"] = round(macd_pts, 1)

    # ---- 均线底部金叉 (20) ----
    ma_pts = 0.0
    if ma5[-1] > ma10[-1] > ma20[-1]:
        ma_pts += 7.0
        tags.append("均线多头")
    if _slope_ratio(ma20, 5) > 0.001:
        ma_pts += 5.0
        tags.append("MA20上翘")
    gc = 0
    for i in range(max(1, n - 10), n):
        if (ma5[i] > ma10[i] and ma5[i - 1] <= ma10[i - 1]) or (ma10[i] > ma20[i] and ma10[i - 1] <= ma20[i - 1]):
            gc += 1
    if gc >= 2:
        ma_pts += 5.0
        tags.append("均线金叉×%d" % gc)
    elif gc == 1:
        ma_pts += 3.0
        tags.append("均线金叉")
    if cur > ma20[-1]:
        ma_pts += 3.0
        tags.append("站上MA20")
    factors["ma"] = round(min(20.0, ma_pts), 1)

    # ---- 量能确认 (15) ----
    vol_pts = 0.0
    if vol_ratio >= 1.2 and vol_ratio <= 1.8:
        vol_pts += 9.0
        tags.append("温和放量")
    elif vol_ratio > 1.8:
        vol_pts += 6.0
    elif vol_ratio >= 1.0:
        vol_pts += 6.0
    else:
        vol_pts += 3.0
    if cur > prev and cur_vol > vols[-2]:
        vol_pts += 5.0
        tags.append("价升量增")
    factors["vol"] = round(min(15.0, vol_pts), 1)

    # ---- 异动回踩 / 首板 (15) ----
    surge_pts = 0.0
    zt_days: list[int] = []
    surge_idx = -1
    for i in range(max(1, n - 12), n):
        up = (closes[i] / closes[i - 1] - 1.0) * 100.0 if closes[i - 1] > 0 else 0.0
        is_zt = up >= 9.5 and abs(highs[i] - closes[i]) < 1e-6
        seg_vol = sum(vols[max(0, i - 20):i]) / max(1, (i - max(0, i - 20)))
        is_big = up >= 7.0 and vols[i] >= 1.5 * seg_vol
        if is_zt:
            zt_days.append(i)
        if (is_zt or is_big) and surge_idx < 0:
            surge_idx = n - 1 - i
    if len(zt_days) == 1 and vols[zt_days[0]] >= 0.3 * avg20_vol:
        surge_pts += 8.0
        tags.append("首板")
    if surge_idx >= 0:
        if 2 <= surge_idx <= 12 and cur >= min(ma10[-1], ma20[-1]):
            recent_vol_avg = sum(vols[-3:]) / 3.0
            if recent_vol_avg <= vols[-1 - surge_idx] * 0.9:
                surge_pts += 7.0
                tags.append("异动回踩支撑")
            else:
                surge_pts += 4.0
                tags.append("异动回踩中")
    factors["surge"] = round(min(15.0, surge_pts), 1)

    # ---- 位置安全边际 (10) ----
    h60 = max(highs[-60:])
    l60 = min(lows[-60:])
    cpos = (cur - l60) / (h60 - l60) if h60 > l60 else 0.5
    pos_pts = 10.0 if cpos < 0.3 else (8.0 if cpos < 0.5 else (5.0 if cpos < 0.75 else 2.0))
    tags.append("位置%d%%" % int(cpos * 100))
    factors["pos"] = pos_pts

    # ---- 趋势环境 (10) ----
    trend_pts = 0.0
    if cur > ma57[-1]:
        trend_pts += 3.0
        tags.append("MA57上方")
    if ma60 is not None and cur > ma60[-1]:
        trend_pts += 2.0
        tags.append("MA60上方")
    if ma144 is not None and ma144[-1] and cur > ma144[-1]:
        trend_pts += 2.0
        tags.append("MA144上方")
        if ma60 is not None and ma60[-1] > ma144[-1]:
            trend_pts += 1.0
            tags.append("季线上穿半年线")
    pct20 = (cur / closes[-21] - 1.0) * 100.0 if n > 21 and closes[-21] > 0 else 0.0
    if 3.0 <= pct20 <= 30.0:
        trend_pts += 5.0
    elif pct20 > 45.0:
        trend_pts = 0.0
    factors["trend"] = min(10.0, trend_pts)

    # ---- RSI 动能位置 (叠加 0-8，超买扣到 0) ----
    rsi_v = _rsi(closes, 14)
    rsi_pts = 0.0
    if rsi_v >= 80:
        rsi_pts = 0.0
        risks.append("RSI超买")
    elif rsi_v >= 65:
        rsi_pts = 4.0
        tags.append("动能偏热")
    elif rsi_v >= 50:
        rsi_pts = 7.0
        tags.append("动能健康")
    elif rsi_v >= 30:
        rsi_pts = 5.0
        tags.append("低位修复")
    else:
        rsi_pts = 4.0
        tags.append("超跌区")
    factors["rsi"] = rsi_pts

    # ---- 量价配合度 (近5日：涨放量+跌缩量为健康，背离扣分) ----
    vp_pts = 0.0
    vp_divergence = False
    for i in range(max(1, n - 5), n):
        chg = closes[i] - closes[i - 1]
        v = vols[i] / avg20_vol if avg20_vol > 0 else 1.0
        if chg > 0 and v >= 1.1:
            vp_pts += 1.6
        elif chg > 0 and v < 0.8:
            vp_pts -= 1.0
            vp_divergence = True
        elif chg < 0 and v <= 0.9:
            vp_pts += 0.8
        elif chg < 0 and v >= 1.2:
            vp_pts -= 1.2
            vp_divergence = True
    vp_pts = max(-4.0, min(8.0, vp_pts))
    if vp_pts >= 4.0:
        tags.append("量价配合")
    elif vp_divergence or vp_pts <= -2.0:
        risks.append("量价背离")
    factors["vp"] = round(vp_pts, 1)

    # ---- 波动蓄势 / 放量突破 (叠加 0-8) ----
    volc_pts = 0.0
    rng20 = _avg_range_pct(highs, lows, closes, 20)
    rng5 = _avg_range_pct(highs, lows, closes, 5)
    h20 = max(highs[-20:]) if n >= 20 else max(highs)
    if rng20 > 0 and rng5 < rng20 * 0.75:
        volc_pts += 4.0
        tags.append("波动收敛")
    if cur >= h20 * 0.999 and vol_ratio >= 1.5:
        volc_pts += 4.0
        tags.append("放量突破")
    if rng20 > 0 and rng5 > rng20 * 2.2:
        volc_pts = max(0.0, volc_pts - 2.0)
        risks.append("波动骤增")
    volc_pts = max(0.0, min(8.0, volc_pts))
    factors["volc"] = round(volc_pts, 1)

    score = max(0.0, min(100.0, sum(factors.values()) + 5.0))

    # ---- 风险标记（本地可算） ----
    name0 = str(name or "").upper()
    if "ST" in name0 or "退" in name0:
        risks.append("ST/退市风险")
    if n >= 4 and (closes[-1] / closes[-4] - 1.0) * 100.0 <= -12.0:
        risks.append("连续下杀")
    dzt = 0
    for i in range(max(1, n - 15), n):
        up = (closes[i] / closes[i - 1] - 1.0) * 100.0 if closes[i - 1] > 0 else 0.0
        if up <= -9.5 and abs(lows[i] - closes[i]) < 1e-6:
            dzt += 1
    if dzt >= 2:
        risks.append("多次跌停")
    if cur < ma20[-1] and _slope_ratio(ma20, 5) < 0:
        risks.append("破位下行")
    if cpos > 0.8 and vol_ratio >= 1.3 and up_pct < 1.0:
        risks.append("高位滞涨")
    if avg5_vol < avg20_vol * 0.4:
        risks.append("量能低迷")

    # ---- 增强风险提示（本地可算，消息面以公告/新闻为准） ----
    if up_pct <= -5.0 and vol_ratio >= 1.5:
        risks.append("放量杀跌")
    rng_today = (highs[-1] - lows[-1]) / cur if cur > 0 else 0.0
    upper_shadow = (highs[-1] - max(closes[-1], prev)) / rng_today if rng_today > 0 else 0.0
    if upper_shadow >= 0.6 and vol_ratio >= 1.3 and up_pct < 2.0:
        risks.append("长上影滞涨")
    for i in range(max(1, n - 5), n):
        up_i = (closes[i] / closes[i - 1] - 1.0) * 100.0 if closes[i - 1] > 0 else 0.0
        if up_i >= 9.5 and highs[i] - closes[i] > 1e-6:
            risks.append("涨停开板")
            break
    if cur <= l60 * 1.001:
        risks.append("创60日新低")
    if cur < ma20[-1] and cur < ma57[-1]:
        risks.append("跌破双均线")
    if n > 6 and closes[-6] > 0 and (cur / closes[-6] - 1.0) * 100.0 >= 20.0:
        risks.append("5日涨幅过大")
    if vol_ratio >= 3.0:
        risks.append("放量过热")

    return {
        "ok": True,
        "score": round(score, 1),
        "factors": factors,
        "tags": tags,
        "risks": risks,
        "red_days": rd,
        "vol_ratio": round(vol_ratio, 2),
        "up_pct": round(up_pct, 2),
        "cpos": round(cpos, 3),
        "latest_time": str(candles[-1].time),
    }
