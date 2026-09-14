# -*- coding: utf-8 -*-
"""Codex 会话健康体检：检测超长会话，自动归档"超长且长期未活跃"的会话。

用法:
  python session_health.py            # 只体检+报告，不自动归档
  python session_health.py --auto     # 体检 + 自动归档（超长且 >3 天未活跃）
                                      #   归档后自动生成续接开场词 + 自动新建续接会话（待确认）
  python session_health.py --no-create # 与 --auto 同用，禁用"自动新建会话"

阈值:
  HOT           rollout > 8MB 或 tokens_used > 120M  -> 提醒（可能接近压缩）
  AUTO_ARCHIVE  rollout > 10MB 且 updated_at 距今 > 3 天 -> 自动归档
"""
import sqlite3
import datetime
import os
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB = r"C:\Users\Admin\.codex\state_5.sqlite"
DB_BACKUP_DIR = r"C:\Users\Admin\.codex\_db_backups"
REPORT_DIR = r"E:\AI24X\ai24x-website\ai24x01\ops\session-health"
HANDOFF_DIR = os.path.join(REPORT_DIR, "续接开场词")
NEW_DIR = os.path.join(REPORT_DIR, "已新建")

NODE = r"D:\Program Files\nodejs\node.exe"
CODEX_JS = r"C:\Users\Admin\AppData\Roaming\npm\node_modules\@openai\codex\bin\codex.js"

HOT_SIZE_MB = 8.0
HOT_TOKENS = 120_000_000
AUTO_SIZE_MB = 10.0
AUTO_INACTIVE_DAYS = 3

CARD_BASE = r"E:\AI24X\帮助指南\最新规划\顶级规划\岗位说明书V2\上岗卡"
MARKETS_CARD = r"E:\AI24X\ai24x-website\ai24x01\p\markets\docs\2026-08-16-上岗卡-AI行情官国际版.md"

# cwd 关键词 -> (角色名, 上岗卡路径)
ROLE_MAP = [
    ("p\\markets", "AI行情官国际版", MARKETS_CARD),
    ("p\\a1", "AI24X行情官", os.path.join(CARD_BASE, "01-AI24X行情官-上岗卡.md")),
    ("p\\game", "AI24X游戏", os.path.join(CARD_BASE, "02-AI24X游戏-上岗卡.md")),
    ("docs\\营销", "AI24X营销", os.path.join(CARD_BASE, "03-AI24X营销-上岗卡.md")),
    ("docs\\安全", "AI24X安全", os.path.join(CARD_BASE, "05-AI24X安全-上岗卡.md")),
]
TITLE_MAP = [
    ("调研", "AI24X调研", os.path.join(CARD_BASE, "04-AI24X调研-上岗卡.md")),
    ("财务", "财务专用", os.path.join(CARD_BASE, "06-财务专用-上岗卡.md")),
    ("token", "AI24X国际token", os.path.join(CARD_BASE, "03-AI24X营销-上岗卡.md")),
]


def fmt_size(mb):
    if mb >= 1024:
        return f"{mb/1024:.1f}GB"
    return f"{mb:.1f}MB"


def resolve_role(title, cwd):
    cwd_l = (cwd or "").lower()
    for kw, role, card in ROLE_MAP:
        if kw in cwd_l:
            return role, card
    t_l = (title or "").lower()
    for kw, role, card in TITLE_MAP:
        if kw in t_l:
            return role, card
    return "项目", os.path.join(CARD_BASE, "00-岗位说明书V2-总纲.md")


def gen_handoff(tid, title, cwd, archived_dt):
    """为已归档会话生成「新会话续接开场词」，返回文件路径或 None。"""
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    role, card = resolve_role(title, cwd)
    cwd = (cwd or "").replace("\\\\?\\", "")
    stamp = archived_dt.strftime("%Y%m%d-%H%M")
    fname = f"{stamp}-{role}-新会话开场词.md"
    fpath = os.path.join(HANDOFF_DIR, fname)
    card_ref = card if os.path.exists(card) else "(上岗卡缺失，改读岗位说明书总纲)"
    body = f"""你是 **{role}** 项目会话。请按以下顺序开工：

1. 读上岗卡：`{card_ref}`
2. 读岗位说明书与目标池：`E:\\AI24X\\帮助指南\\最新规划\\顶级规划\\岗位说明书V2\\`（00-总纲 + 对应岗位说明书 + 目标池.md）
3. 接续上一次工作：原会话「{title}」已于 {archived_dt.strftime("%Y-%m-%d %H:%M")} 归档，项目文档请从以下位置读取续接：
   - 项目决策/待办/踩坑：`帮助指南\\最新规划\\`（分类+日期戳）
   - 每日回执：项目 `收发\\回复\\`
   - 执行产物：`ops\\`
   - 工作目录：`{cwd}`
4. 开工后按红绿灯自查（🟢自主 🟡告警 🔴请示），收尾回执：✅ 完成 / ⚠️ 卡点 / 🆕 发现。

纪律：会话是工作台不是仓库，本阶段完成后把关键状态落盘、回执，即可再次归档换新。
"""
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"# 新会话续接开场词 · {role}（{archived_dt.strftime('%Y-%m-%d %H:%M')}）\n\n")
        f.write("> 由「会话健康体检」自动生成：原会话已归档，以下为续接开场词。\n")
        f.write("> 用法：新建 Codex 会话后，把下方正文整段作为第一条消息发出；或由主脑目标派发时引用本文件。\n\n")
        f.write("---\n\n")
        f.write(body)
        f.write("\n---\n\n*AI24X 指挥中心 · 会话健康体检自动生成*\n")
    return fpath


def norm_cwd(cwd):
    return (cwd or "").replace("\\\\?\\", "")


def already_created_today(cur, cwd, now):
    """该工作目录今天是否已有活跃新会话（防重复自动创建）。"""
    start = datetime.datetime(now.year, now.month, now.day).timestamp() * 1000
    n = cur.execute(
        "SELECT COUNT(*) FROM threads WHERE archived=0 AND created_at_ms > ? AND cwd LIKE ?",
        (start, "%" + cwd),
    ).fetchone()[0]
    return n > 0


def create_session(cwd, role, handoff_path, now):
    """用 node 直调 codex exec 自动新建续接会话，返回 (ok, last_msg)。"""
    os.makedirs(NEW_DIR, exist_ok=True)
    stamp = now.strftime("%Y%m%d-%H%M")
    out_file = os.path.join(NEW_DIR, f"{stamp}-{role}-新建回执.txt")
    prompt = (
        f"你是 {role} 项目会话（由会话健康体检自动创建，待雷总确认）。\n"
        f"请先读取续接开场词文件：{handoff_path}，按其中指引开工。\n"
        f"现在只回复一行：{role} 会话已就绪 ✅\n"
    )
    cmd = [NODE, CODEX_JS, "exec", "-C", cwd, "-s", "danger-full-access", "--json", "-o", out_file, prompt]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=240)
        ok = r.returncode == 0
    except Exception as e:
        ok = False
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(f"创建失败：{e}\n")
        except Exception:
            pass
    last_msg = ""
    if os.path.exists(out_file):
        try:
            with open(out_file, encoding="utf-8") as f:
                last_msg = f.read().strip()[:200]
        except Exception:
            pass
    return ok, last_msg


def main():
    auto = "--auto" in sys.argv
    gen_only = "--gen-handoff" in sys.argv
    no_create = "--no-create" in sys.argv
    now = datetime.datetime.now()
    today = now.strftime("%Y%m%d")
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(DB_BACKUP_DIR, exist_ok=True)
    os.makedirs(NEW_DIR, exist_ok=True)

    con = sqlite3.connect(DB)
    cur = con.cursor()

    if gen_only:
        # 为最近归档的会话补生成续接开场词
        cutoff = (now - datetime.timedelta(days=30)).timestamp() * 1000
        rows = cur.execute(
            "SELECT id, title, cwd, archived_at FROM threads "
            "WHERE archived=1 AND archived_at IS NOT NULL ORDER BY archived_at DESC LIMIT 12"
        ).fetchall()
        made = []
        for tid, title, cwd, aa in rows:
            if not aa or aa < cutoff:
                continue
            dt = datetime.datetime.fromtimestamp(aa / 1000) if aa else now
            fp = gen_handoff(tid, title, cwd, dt)
            if fp:
                made.append(os.path.basename(fp))
        con.close()
        try:
            for m in made:
                print("handoff:", m)
            print(f"handoff_count: {len(made)}")
        except Exception:
            pass
        return

    rows = cur.execute(
        "SELECT id, title, cwd, rollout_path, tokens_used, updated_at_ms, archived "
        "FROM threads WHERE archived=0 ORDER BY updated_at_ms DESC"
    ).fetchall()

    hot = []
    to_archive = []
    normal = []
    for tid, title, cwd, rp, tokens, up, arch in rows:
        title = (title or "(no title)").replace("\n", " ")[:40]
        cwd = (cwd or "").replace("\\\\?\\", "")
        size = os.path.getsize(rp) / 1024 / 1024 if rp and os.path.exists(rp) else 0.0
        tokens = tokens or 0
        up_dt = datetime.datetime.fromtimestamp(up / 1000) if up else now
        inactive_days = (now - up_dt).total_seconds() / 86400
        item = (tid, title, cwd, size, tokens, up_dt, inactive_days)
        if size > AUTO_SIZE_MB and inactive_days > AUTO_INACTIVE_DAYS:
            to_archive.append(item)
        elif size > HOT_SIZE_MB or tokens > HOT_TOKENS:
            hot.append(item)
        else:
            normal.append(item)

    lines = []
    lines.append(f"# 会话健康体检 · {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"- 模式：{'自动归档' if auto else '仅体检'}")
    lines.append(f"- 未归档会话总数：{len(rows)}（超长提醒 {len(hot)} ｜ 待自动归档 {len(to_archive)} ｜ 正常 {len(normal)}）")
    lines.append("")

    lines.append("## 待自动归档（超长 + >3 天未活跃）")
    if to_archive:
        for tid, title, cwd, size, tokens, up_dt, inactive in to_archive:
            lines.append(f"- [{title}] size={fmt_size(size)} 累计tokens={tokens:,} 最后活跃={up_dt:%m-%d %H:%M} 闲置{inactive:.0f}天 cwd={cwd}")
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 超长提醒（活跃中，不自动动）")
    if hot:
        for tid, title, cwd, size, tokens, up_dt, inactive in hot:
            lines.append(f"- [{title}] size={fmt_size(size)} 累计tokens={tokens:,} 最后活跃={up_dt:%m-%d %H:%M} cwd={cwd}")
    else:
        lines.append("- 无")
    lines.append("")

    if auto and to_archive:
        # 改库前备份
        backup = os.path.join(DB_BACKUP_DIR, f"state_5_{today}_{now:%H%M%S}.sqlite")
        shutil.copy2(DB, backup)
        lines.append(f"## 自动归档执行（DB 备份：{backup}）")
        for tid, title, cwd, size, tokens, up_dt, inactive in to_archive:
            cur.execute(
                "UPDATE threads SET archived=1, archived_at=? WHERE id=?",
                (int(now.timestamp() * 1000), tid),
            )
            lines.append(f"- ✅ 已归档 [{title}]（{fmt_size(size)}，闲置{inactive:.0f}天）")
        con.commit()
        # 归档后自动生成续接开场词
        handoffs = []
        for tid, title, cwd, size, tokens, up_dt, inactive in to_archive:
            fp = gen_handoff(tid, title, cwd, now)
            if fp:
                lines.append(f"- 📋 已生成续接开场词：`{os.path.basename(fp)}`")
                role, _ = resolve_role(title, cwd)
                handoffs.append((title, norm_cwd(cwd), fp, role))
        lines.append("")

        # 自动新建续接会话（待确认；默认开启，--no-create 关闭）
        if no_create:
            lines.append("## 自动新建会话：已禁用（--no-create）")
            lines.append("")
        elif handoffs:
            lines.append("## 自动新建续接会话（待雷总确认）")
            for title, cwd, fp, role in handoffs:
                if already_created_today(cur, cwd, now):
                    lines.append(f"- ⏭️ [{role}] 今日已有新会话，跳过自动新建")
                    continue
                ok, msg = create_session(cwd, role, fp, now)
                if ok:
                    lines.append(f"- 🆕 已自动新建 [{role}] 会话（cwd={cwd}），重启 Codex 后可见；回执：{msg}")
                else:
                    lines.append(f"- ⚠️ [{role}] 自动新建失败，开场词已就绪（`{os.path.basename(fp)}`），可手动新建")
            lines.append("")
        lines.append("")

    report = os.path.join(REPORT_DIR, f"session-health-{today}.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    con.close()
    try:
        print(f"report: {report}")
        if to_archive:
            print(f"to_archive: {len(to_archive)}" + (" (done)" if auto else " (need --auto)"))
        if hot:
            print(f"hot: {len(hot)}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
