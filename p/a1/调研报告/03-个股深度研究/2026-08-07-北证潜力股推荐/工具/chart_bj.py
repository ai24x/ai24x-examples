# -*- coding: utf-8 -*-
# 用途：北证潜力股推荐 —— 生成 科达自控(920932) + 科隆新材(920098) + 灵鸽科技(920284) 日K线图
import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
FP = font_manager.FontProperties(fname=FONT_PATH)
plt.rcParams["axes.unicode_minus"] = False
RED = "#e53935"; GREEN = "#2e7d32"; GRAY = "#9e9e9e"

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.dirname(TOOL_DIR)
DATA_DIR = os.path.join(REPORT_DIR, "数据")

with open(os.path.join(DATA_DIR, "klines_20260807.json"), "r", encoding="utf-8") as f:
    K = json.load(f)

def load(code):
    bars = K[code]["bars"]
    rows = []
    for r in bars:
        rows.append({"date": r[0], "open": float(r[1]), "close": float(r[2]),
                     "high": float(r[3]), "low": float(r[4]), "vol": float(r[5])})
    return rows

def draw(data, title, out, levels, stats_lines):
    n = len(data)
    x = np.arange(n)
    o = np.array([d["open"] for d in data]); c = np.array([d["close"] for d in data])
    h = np.array([d["high"] for d in data]); l = np.array([d["low"] for d in data])
    v = np.array([d["vol"] for d in data]) / 1e4

    def ma(p):
        k = np.ones(p) / p
        m = np.convolve(c, k, mode="full")[:n]
        m[:p - 1] = np.nan
        return m

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06})
    for i in range(n):
        color = RED if c[i] >= o[i] else GREEN
        ax.add_patch(Rectangle((i - 0.32, min(o[i], c[i])), 0.64, abs(c[i] - o[i]) or 0.01,
                               facecolor=color, edgecolor=color, linewidth=0.5, zorder=3))
        ax.plot([i, i], [l[i], h[i]], color=color, linewidth=0.8, zorder=2)
    ax.plot(x, ma(5), color="#fb8c00", linewidth=1.2, label="MA5")
    ax.plot(x, ma(10), color="#1e88e5", linewidth=1.2, label="MA10")
    ax.plot(x, ma(20), color="#8e24aa", linewidth=1.2, label="MA20")

    for lv, lab, col in levels:
        ax.axhline(lv, color=col, linestyle="--", linewidth=1.0, alpha=0.8)
        ax.text(0.3, lv, lab, fontproperties=FP, fontsize=10, color=col, va="bottom",
                bbox=dict(facecolor="white", alpha=0.75, edgecolor=col, linewidth=0.6))

    last = c[-1]
    ax.annotate(f"{last:.2f}", xy=(n - 1, last), xytext=(n - 1 + 0.4, last),
                fontproperties=FP, fontsize=11, color="black", fontweight="bold")
    ax.set_title(title, fontproperties=FP, fontsize=15, fontweight="bold", pad=10)
    ax.legend(prop=FP, loc="upper left", fontsize=9, framealpha=0.8)
    ax.set_ylabel("价格 (元)", fontproperties=FP, fontsize=10)
    ax.grid(alpha=0.25, linestyle=":")

    for i in range(n):
        color = RED if c[i] >= o[i] else GREEN
        axv.bar(i, v[i], color=color, alpha=0.75, width=0.65)
    axv.set_ylabel("成交量(万手)", fontproperties=FP, fontsize=10)
    axv.grid(alpha=0.25, linestyle=":")

    txt = "\n".join(stats_lines)
    fig.text(0.015, 0.015, txt, fontproperties=FP, fontsize=9.5, va="bottom",
             bbox=dict(facecolor="#f5f5f5", edgecolor=GRAY, linewidth=0.8, alpha=0.95))

    xt = range(0, n, 5)
    plt.xticks(xt, [data[i]["date"] for i in xt], fontproperties=FP, fontsize=8.5)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("saved", out)

kdz = load("920932")[-60:]
draw(kdz, "科达自控(920932) 日K 近60日 —— 矿山具身智能机器人·智慧矿山小市值龙头",
     os.path.join(REPORT_DIR, "chart_920932.png"),
     levels=[(13.39, "压力13.39(MA50)", "#ad1457"), (13.20, "压力13.20(8/6高)", "#c62828"),
             (12.34, "支撑12.34(8/6低)", "#2e7d32"), (12.05, "支撑12.05(8/5低)", "#2e7d32")],
     stats_lines=["8/6: 收13.06 (+3.16%)  量3.68万手 (5日量/20日量=1.57 持续放量)",
                  "连续5日阳线站上MA20 | 位置30% 距MA50(13.39)一步之遥, 突破即打开空间",
                  "MA5=12.31 MA10=11.58 MA20=11.44 | MACD翻红第8天·均线多头·价升量增",
                  "AI行情官评分73.2(北证候选组最高) | 总市值约13.8亿 | 无风险标签"])

klx = load("920098")[-60:]
draw(klx, "科隆新材(920098) 日K 近60日 —— 8/6放量突破·煤机橡塑密封件小巨人",
     os.path.join(REPORT_DIR, "chart_920098.png"),
     levels=[(19.03, "压力19.03(MA50)", "#ad1457"), (18.45, "压力18.45(8/6高)", "#c62828"),
             (16.84, "支撑16.84(8/6低)", "#2e7d32"), (16.69, "支撑16.69(MA20)", "#2e7d32")],
     stats_lines=["8/6: 收17.95 (+4.18%)  量1.95万手 (较5日均量约3.6倍 放量突破)",
                  "平台整理后首次放量突破前高 | 5日累计+8.26% 未过热",
                  "MA5=17.29 MA10=16.86 MA20=16.69 | MACD翻红第16天·均线多头·价升量增",
                  "AI行情官评分65.4 | 总市值约14.6亿 | 无风险标签"])

lg = load("920284")[-60:]
draw(lg, "灵鸽科技(920284) 日K 近60日 —— 锂电干法电极产线·8/5放量后缩量回踩企稳",
     os.path.join(REPORT_DIR, "chart_920284.png"),
     levels=[(19.90, "压力19.90(7/29高)", "#ad1457"), (19.38, "压力19.38(8/6高)", "#c62828"),
             (18.60, "支撑18.60(8/6低)", "#2e7d32"), (17.45, "支撑17.45(8/5低)", "#2e7d32")],
     stats_lines=["8/6: 收19.07 (-0.16%)  量3.20万手 (较8/5缩量约4成 良性回踩)",
                  "8/5放量+8.40%后缩量回踩不破18.60 | 位置19% 三只中最低",
                  "MA5=18.25 MA10=17.50 MA20=16.74 | MACD翻红第12天·均线多头",
                  "AI行情官评分65.2 | 总市值约20.0亿 | 无风险标签"])