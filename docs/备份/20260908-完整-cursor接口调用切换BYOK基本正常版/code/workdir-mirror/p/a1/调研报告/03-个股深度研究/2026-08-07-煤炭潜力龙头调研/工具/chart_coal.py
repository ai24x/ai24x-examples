# -*- coding: utf-8 -*-
# 用途：煤炭潜力龙头 —— 生成 盘江股份(600395) + 山西焦化(600740) 日K线图
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
    ax.set_title(title, fontproperties=FP, fontsize=16, fontweight="bold", pad=10)
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

panjiang = load("600395")[-60:]
draw(panjiang, "盘江股份(600395) 日K 近60日 —— 8/6放量突破前高·西南焦煤龙头",
     os.path.join(REPORT_DIR, "chart_600395.png"),
     levels=[(5.30, "压力5.20-5.30", "#ad1457"), (5.13, "压力5.13(8/6高)", "#c62828"),
             (4.99, "支撑4.91-4.99(前平台)", "#2e7d32"), (4.77, "支撑4.77(MA20)", "#2e7d32")],
     stats_lines=["8/6: 收5.06 (+4.1%)  量68.8万手(放量突破)",
                  "8/6放量突破前高4.99 | 5日累计仅+2.9% (未过热)",
                  "MA5=4.93 MA10=4.85 MA20=4.77 | MACD翻红第20天·均线多头·价升量增",
                  "AI行情官评分65.0 | 总市值约109亿 | 无风险标签"])

shanxi = load("600740")[-60:]
draw(shanxi, "山西焦化(600740) 日K 近60日 —— 横盘蓄势后放量突破·焦炭龙头",
     os.path.join(REPORT_DIR, "chart_600740.png"),
     levels=[(3.70, "压力3.70整数关", "#ad1457"), (3.66, "压力3.66-3.67(8/6高)", "#c62828"),
             (3.51, "支撑3.51-3.54(8/6低)", "#2e7d32"), (3.47, "支撑3.47(MA10/20区)", "#2e7d32")],
     stats_lines=["8/6: 收3.62 (+2.3%)  量47.4万手(较前日近翻倍)",
                  "7月下旬起横盘蓄势、5日涨幅0% (刚启动) | 8/6温和放量突破",
                  "MA5=3.60 MA10=3.57 MA20=3.53 | MACD翻红第24天·均线多头·动能健康",
                  "AI行情官评分76.2(煤炭组最高) | 总市值约93亿 | 无风险标签"])