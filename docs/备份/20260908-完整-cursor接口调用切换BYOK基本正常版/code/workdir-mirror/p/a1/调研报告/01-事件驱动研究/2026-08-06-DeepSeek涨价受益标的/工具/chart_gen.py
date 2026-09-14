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

lt = load(os.path.join(DATA_DIR, "k_litong.json"))
uc = load(os.path.join(DATA_DIR, "k_ucloud.json"))

draw(lt, "利通电子(603629) 日K 2026-06-01 ~ 2026-08-06 —— DeepSeek涨价受益·业绩龙头",
     os.path.join(REPORT_DIR, "chart_litong.png"),
     levels=[(124.0, "压力124(8/6高)", "#c62828"), (130.2, "压力130(7/23高)", "#ad1457"),
             (112.0, "支撑112(8/6低)", "#2e7d32"), (105.5, "支撑MA5/105", "#2e7d32")],
     stats_lines=["8/6: 收122.52 (+8.76%)  量76.8万手/92.7亿(量比2.07)",
                  "5日累计 +40.4% | 4天3板(7/31、8/4、8/5涨停)",
                  "MA5=105.3  MA10=103.8  MA20=106.2 | MACD金叉扩张  RSI14=50.2",
                  "H1净利6.5-7.5亿(+1173%~1368%) | 算力云合同36个月+ | 13家机构调研"])

draw(uc, "优刻得(688158) 日K 2026-06-01 ~ 2026-08-06 —— DeepSeek涨价受益·正宗云厂商",
     os.path.join(REPORT_DIR, "chart_ucloud.png"),
     levels=[(36.2, "压力36.2(8/6高)", "#c62828"), (38.0, "压力37-39.3(7月三顶区)", "#ad1457"),
             (33.6, "支撑MA5/33.6", "#2e7d32"), (31.4, "支撑MA10/31.4", "#2e7d32")],
     stats_lines=["8/6: 收35.24 (-0.31%)  量33.5万手/11.9亿(缩量回踩)",
                  "5日累计 +32.6% | 7/31 +15.76%、8/4 +11.99%放量突破",
                  "MA5=33.6  MA10=31.0  MA20=31.9 | MACD金叉  RSI14=57.1",
                  "市值约166亿·科创板20cm | 7/31-8/4异动龙虎榜净买5194万 | 距前高40.3约+14%"])
