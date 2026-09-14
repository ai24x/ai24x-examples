"""AI Brief 合规抽检脚本（P0 措辞铁律）。
扫描 markets 已生成的 brief 缓存（data/cache/brief_*.json），
用与 ai_brief.py 完全一致的黑名单做后置校验，输出合规报告。
用法：python audit_briefs.py [--limit 100] [--out <path>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_APP = ROOT / "api" / "server" / "app"
CACHE_DIR = ROOT / "api" / "server" / "data" / "cache"
DEFAULT_OUT = ROOT / "ops"

sys.path.insert(0, str(API_APP))

try:
    from app import ai_brief  # 与生产完全同源，保证口径一致

    FORBIDDEN_RE = ai_brief._FORBIDDEN_RE
    NEUTRALIZE_PHRASES = ai_brief._NEUTRALIZE_PHRASES
    SOURCE = "ai_brief module"
except Exception as exc:  # 导入失败时降级为内联同款正则（必须与 ai_brief.py 保持同步）
    FORBIDDEN_RE = re.compile(
        r"\b("
        r"buy|sell|hold|accumulate|avoid|recommend|recommendation|signal|signals|"
        r"target|targets|guarantee|guaranteed|tips|picks|broker|"
        r"trade|trading|you should|you must|you can profit|don't miss"
        r")\b",
        re.IGNORECASE,
    )
    NEUTRALIZE_PHRASES = (
        ("trading below", "price below"),
        ("trading above", "price above"),
        ("trading around", "price around"),
        ("trading near", "price near"),
        ("trading at", "price at"),
        ("trading in", "price in"),
        ("trading within", "price within"),
        ("trading range", "price range"),
        ("trading session", "session"),
        ("trading day", "day"),
        ("signal line", "DEA line"),
        ("signal lines", "DEA lines"),
    )
    SOURCE = f"inline fallback ({type(exc).__name__})"


def check_brief(text: str):
    """返回 (neutralized_text, hits, hit_words)。"""
    for src, dst in NEUTRALIZE_PHRASES:
        text = re.sub(re.escape(src), dst, text, flags=re.IGNORECASE)
    hits = 0
    hit_words = []
    for line in text.splitlines():
        found = FORBIDDEN_RE.findall(line)
        if found:
            hits += len(found)
            hit_words.extend(w.lower() for w in found)
    return text, hits, hit_words


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    files = sorted(CACHE_DIR.glob("brief_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[: args.limit]
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"brief-compliance-{day}.md"

    rows = []
    violations = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                obj = json.load(fh)
        except Exception as exc:
            rows.append({"file": fp.name, "error": str(exc)})
            continue
        brief = obj.get("brief") or ""
        _, hits, hit_words = check_brief(brief)
        row = {
            "file": fp.name,
            "symbol": obj.get("symbol"),
            "period": obj.get("period"),
            "mode": obj.get("mode"),
            "generated_at": obj.get("generated_at"),
            "hits": hits,
            "hit_words": sorted(set(hit_words)),
            "len": len(brief),
        }
        rows.append(row)
        if hits:
            violations.append(row)

    n = len([r for r in rows if "error" not in r])
    lines = [
        f"# AI Brief 合规抽检报告 · {day}",
        "",
        f"- 扫描范围：`{CACHE_DIR}` `brief_*.json`（最近 {len(files)} 个文件）",
        f"- 有效点评数：**{n}**",
        f"- 违规数：**{len(violations)}**",
        f"- 黑名单口径：`{SOURCE}`（命中即按语境判定，生产链路命中>0 会降级为兜底模板）",
        f"- 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
    ]
    lines.append("## 违规明细")
    if violations:
        for v in violations:
            lines.append(
                f"- `{v['file']}` | {v['symbol']} {v['period']} | mode={v['mode']} | "
                f"hits={v['hits']} | 命中词: {', '.join(v['hit_words'])}"
            )
    else:
        lines.append("- 无（0 条违规）")
    lines.append("")
    lines.append("## 命中词示例统计（全部扫描内出现过的禁用词）")
    all_words: dict[str, int] = {}
    for r in rows:
        for w in r.get("hit_words", []):
            all_words[w] = all_words.get(w, 0) + 1
    if all_words:
        for w, c in sorted(all_words.items(), key=lambda kv: -kv[1]):
            lines.append(f"- `{w}` x {c}")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("> 注：报告仅统计已落盘缓存；mode=ai 表示模型原生输出通过校验，fallback_* 表示命中黑名单/出错后已降级为合规模板。")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"scanned={len(files)} valid={n} violations={len(violations)}")
    print(f"report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
