# -*- coding: utf-8 -*-
# 用途：DeepSeek涨价低风险优选 —— 生成 立昂技术(300603) + 金信诺(300252) 日K线图
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

liang = load("300603")[-60:]
draw(liang, "立昂技术(300603) 日K 近60日 —— 底部5连阳后缩量整理·自营算力中心",
     os.path.join(REPORT_DIR, "chart_300603.png"),
     levels=[(8.50, "压力8.50整数关", "#ad1457"), (8.28, "压力8.17-8.28", "#c62828"),
             (7.93, "支撑7.93-7.97", "#2e7d32"), (7.75, "支撑7.75(MA10)", "#2e7d32")],
     stats_lines=["8/6: 收8.09 (-0.2%)  量10.5万手(缩量整理)",
                  "5日累计 +8.9% (温和) | 8/4高点8.28 | 8/5-8/6缩量回踩不破",
                  "MA5=8.00 MA10=7.75 MA20=7.51 | MACD翻红第22天·金叉×2·均线多头",
                  "AI行情官评分65.0 | 流通市值约30亿/总38亿 | 无风险标签"])

jinx = load("300252")[-60:]
draw(jinx, "金信诺(300252) 日K 近60日 —— 底部5连阳温和放量·AI高速互联",
     os.path.join(REPORT_DIR, "chart_300252.png"),
     levels=[(12.50, "压力12.5平台", "#ad1457"), (11.94, "压力11.94(8/6高)", "#c62828"),
             (11.48, "支撑11.48(8/6低)", "#2e7d32"), (11.35, "支撑11.35-11.39(MA5/20)", "#2e7d32")],
     stats_lines=["8/6: 收11.83 (+1.5%)  量30.1万手(温和)",
                  "5日累计 +14.0% | 7/31起底部5连阳(+4.0/+2.8/+2.5/+2.5/+1.5%)",
                  "MA5=11.35 MA10=11.00 MA20=11.39 | MACD翻红第5天·金叉·红柱放大",
                  "AI行情官评分56.6 | 流通市值约66亿/总81亿 | 无风险标签"])