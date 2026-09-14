# -*- coding: utf-8 -*-
# 用途：把报告 md 转成"单文件分享版 HTML"（图片内嵌 base64，无外部依赖）。
# 用法：python make_share.py   （自动找到报告文件夹内最新的 *.md）
# 说明：图片与报告同级，或放 数据/ 同级均可；输出到 分享版/。
import base64
import glob
import os
import re
import sys

import markdown

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.dirname(TOOL_DIR)
SHARE_DIR = os.path.join(REPORT_DIR, "分享版")
os.makedirs(SHARE_DIR, exist_ok=True)

mds = sorted(glob.glob(os.path.join(REPORT_DIR, "*.md")))
if not mds:
    raise SystemExit("报告文件夹内未找到 md 文件: " + REPORT_DIR)
MD = sys.argv[1] if len(sys.argv) > 1 else mds[-1]
NAME = os.path.splitext(os.path.basename(MD))[0]

with open(MD, encoding="utf-8") as f:
    md_text = f.read()

first_line = md_text.splitlines()[0]
title = first_line.lstrip("# ").strip()
body = re.sub(r"^# .*\n", "", md_text, count=1)

# 从 md 中提取「数据截至」日期，避免 banner 显示写死的旧日期
mdate = re.search(r"数据截至\s*(\d{4}-\d{2}-\d{2})", md_text)
meta_date = mdate.group(1) + " 收盘" if mdate else "最新收盘"

html_body = markdown.markdown(body, extensions=["tables", "fenced_code", "sane_lists"])

def embed_img(m):
    alt, src = m.group(1), m.group(2)
    rel = src.lstrip("./").replace("/", os.sep)
    fp = os.path.join(REPORT_DIR, rel)
    if os.path.exists(fp):
        with open(fp, "rb") as im:
            b64 = base64.b64encode(im.read()).decode("ascii")
        return '<img alt="%s" src="data:image/png;base64,%s" />' % (alt, b64)
    return m.group(0)

html_body = re.sub(r'<img alt="([^"]*)" src="([^"]+)"\s*/>', embed_img, html_body)

# 自动嵌入「信号分享卡」（分享卡_*.png，可选）：整卡以 base64 内嵌，保持单文件分享
def _card_keep(fp):
    m = re.search(r"_(\d{6})\.png$", os.path.basename(fp))
    return (m is None) or (m.group(1) in md_text)
cards = [fp for fp in sorted(glob.glob(os.path.join(REPORT_DIR, "分享卡_*.png"))) if _card_keep(fp)]
if cards:
    cards_html = ['<div class="share-cards">',
                  '<h2>AI行情官 · 信号分享卡</h2>',
                  '<p class="meta">来自 AI行情官「信号分享卡」模块（K线信号 + 技术快照评分，仅统计非推荐）。</p>']
    for fp in cards:
        with open(fp, "rb") as im:
            b64 = base64.b64encode(im.read()).decode("ascii")
        cap = os.path.splitext(os.path.basename(fp))[0]
        cards_html.append('<img alt="%s" src="data:image/png;base64,%s" />' % (cap, b64))
    html_body = html_body.rstrip() + "\n" + "\n".join(cards_html) + "\n</div>"


CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { margin: 0; background: #eef1f5; font-family: "Microsoft YaHei", "PingFang SC", "SimHei", "Noto Sans CJK SC", sans-serif; color: #1f2430; line-height: 1.75; }
.wrap { max-width: 860px; margin: 0 auto; padding: 18px 12px 40px; }
.paper { background: #ffffff; padding: 40px 46px; box-shadow: 0 2px 14px rgba(20,30,60,.10); border-radius: 4px; }
.banner { border-bottom: 3px solid #c62828; padding-bottom: 14px; margin-bottom: 18px; }
.banner .tag { display: inline-block; background: #c62828; color: #fff; font-size: 12px; padding: 3px 12px; border-radius: 999px; margin-bottom: 10px; letter-spacing: 1px; }
h1 { font-size: 26px; margin: 6px 0 4px; line-height: 1.4; }
.meta { color: #5a6472; font-size: 13px; }
.disclaimer { background: #fff7e6; border: 1px solid #ffd591; color: #8a5b00; font-size: 13px; padding: 10px 14px; border-radius: 6px; margin: 14px 0 6px; }
h2 { font-size: 20px; border-left: 4px solid #c62828; padding-left: 10px; margin: 34px 0 14px; }
h3 { font-size: 16px; margin: 24px 0 10px; color: #0d3b66; }
p { margin: 8px 0; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; margin: 12px 0; }
th, td { border: 1px solid #d5dae2; padding: 7px 10px; text-align: left; vertical-align: top; }
th { background: #f2f5f9; font-weight: 600; }
tr:nth-child(even) td { background: #fafbfd; }
blockquote { margin: 12px 0; padding: 10px 16px; background: #f6f8fa; border-left: 4px solid #90a4ae; color: #44505c; font-size: 13.5px; }
img { max-width: 100%; height: auto; border: 1px solid #e2e6ec; border-radius: 6px; margin: 10px 0; }
.share-cards { page-break-before: always; break-before: page; }
.share-cards h2, .share-cards p { page-break-after: avoid; break-after: avoid; }
.share-cards img { display: block; max-width: 80%; height: auto; margin: 8px auto 0; }
.share-cards img + img { margin-top: 12px; }
hr { border: none; border-top: 1px solid #e2e6ec; margin: 26px 0; }
strong { color: #111827; }
.footer { margin-top: 30px; padding-top: 12px; border-top: 1px dashed #c9cfd8; color: #8a919c; font-size: 12px; text-align: center; }
@media print {
  body { background: #fff; }
  .wrap { padding: 0; }
  .paper { box-shadow: none; padding: 0; }
}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap"><div class="paper">
<div class="banner">
  <span class="tag">AI行情官 · 调研报告</span>
  <h1>{title}</h1>
  <div class="meta">数据截至 {meta_date} · 仅供研究参考</div>
</div>
<div class="disclaimer"><b>重要声明：</b>本报告仅为研究与信息整理，不构成任何投资建议；股市有风险，入市需谨慎。</div>
{body}
<div class="footer">AI行情官智能体生成 · 单文件分享版（图片已内嵌）</div>
</div></div>
</body>
</html>""".format(title=title, meta_date=meta_date, css=CSS, body=html_body)

out = os.path.join(SHARE_DIR, NAME + ".html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print("HTML:", out)
print("SIZE:", os.path.getsize(out), "bytes")
print("URI:", "file:///" + out.replace("\\", "/"))
