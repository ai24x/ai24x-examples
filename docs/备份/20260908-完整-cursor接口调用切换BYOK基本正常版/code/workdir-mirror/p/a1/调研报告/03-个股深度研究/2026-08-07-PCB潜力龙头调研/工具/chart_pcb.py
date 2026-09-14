# -*- coding: utf-8 -*-
# 用途：为报告生成日K线图（红涨绿跌）。数据放报告目录 数据/，图输出到报告目录。
# 用法：python chart_gen.py
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

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))   # 工具/
REPORT_DIR = os.path.dirname(TOOL_DIR)                  # 报告文件夹
DATA_DIR = os.path.join(REPORT_DIR, "数据")

def load(fp):
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)

def draw(data, title, out, levels, stats_lines):
    n = len(data)
    x = np.arange(n)
    o = np.array([d["open"] for d in data]); c = np.array([d["close"] for d in data])
    h = np.array([d["high"] for d in data]); l = np.array([d["low"] for d in data])
    v = np.array([d["vol"] for d in data]) / 1e4  # 万手

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


lt = load(os.path.join(DATA_DIR, "k_002916.json"))
draw(lt, "深南电路(002916) 日K 2026-06-03 ~ 2026-08-06 —— PCB龙头·AI载板高多层",
     os.path.join(REPORT_DIR, "chart_shennan.png"),
     levels=[(367.3, "压力367(8/6高)", "#c62828"), (380.0, "压力380关口", "#ad1457"),
             (338.0, "支撑338(8/6低)", "#2e7d32"), (328.0, "支撑328(8/5低/MA10)", "#2e7d32")],
     stats_lines=["8/6: 收353.99 (+1.38%)  量10.7万手 (冲高367回落)",
                  "5日累计 +24.4% | 8/4涨停+10% 启动",
                  "MA5=329.2  MA10=325.1  MA20=345.2 | MACD翻红第2天·金叉·站上MA20",
                  "AI行情官评分69.4 | PE≈66 | 总市值约2411亿"])

uc = load(os.path.join(DATA_DIR, "k_002463.json"))
draw(uc, "沪电股份(002463) 日K 2026-06-03 ~ 2026-08-06 —— PCB龙头·AI PCB纯度最高",
     os.path.join(REPORT_DIR, "chart_hudian.png"),
     levels=[(122.0, "压力122(8/6高)", "#c62828"), (128.0, "压力128(6月平台)", "#ad1457"),
             (112.0, "支撑112(8/6低)", "#2e7d32"), (108.7, "支撑MA10/108.7", "#2e7d32")],
     stats_lines=["8/6: 收117.20 (+1.38%)  量58.9万手 (缩量整理)",
                  "5日累计 +21.4% (PCB龙头中涨幅最温和) | 8/4涨停启动",
                  "MA5=110.0  MA10=108.7  MA20=117.4 | MACD翻红第1天·金叉·站上MA20",
                  "AI行情官评分63.4 | PE≈52 | 总市值约2255亿"])