# -*- coding: utf-8 -*-
"""Organize root/docs markdown into docs/{规划,开发,决策,联调,历史}."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).name.startswith("scripts")) else Path.cwd()
# when run from repo root:
ROOT = Path.cwd()
DOCS = ROOT / "docs"

for d in ("规划", "开发", "决策", "联调", "历史", "运维"):
    (DOCS / d).mkdir(parents=True, exist_ok=True)


def stub(old: Path, new: Path) -> None:
    rel = Path(os_rel(old, new))
    old.write_text(
        f"# 已迁移\n\n现行文档请打开：[`{new.as_posix()}`]({rel.as_posix()})\n",
        encoding="utf-8",
    )


def os_rel(old: Path, new: Path) -> str:
    try:
        return str(Path(os.path.relpath(new, start=old.parent)).as_posix())  # type: ignore[name-defined]
    except Exception:
        return new.as_posix()


import os


def move(src: str, dst: str, *, write_stub: bool = True) -> None:
    s, d = ROOT / src, ROOT / dst
    if not s.exists():
        print("skip missing", src)
        return
    d.parent.mkdir(parents=True, exist_ok=True)
    if d.exists():
        # if same file content skip; else keep dest, stub source if still there as file to move
        if s.resolve() == d.resolve():
            print("same", src)
            return
        print("dest exists, stub only", dst)
        if write_stub and s.exists() and s.is_file() and s.resolve() != d.resolve():
            # replace source with stub pointing to dest
            s.write_text(
                f"# 已迁移\n\n现行文档请打开：`{dst}`\n",
                encoding="utf-8",
            )
        return
    shutil.move(str(s), str(d))
    print("moved", src, "->", dst)
    if write_stub:
        stub(s, d)


# 1) remove duplicate 总纲 under 开发
dup = DOCS / "开发" / "开发总纲-AI24X-API-v3.5.md"
canon = DOCS / "规划" / "开发总纲-AI24X-API-v3.5.md"
if dup.exists() and canon.exists():
    hist = DOCS / "历史" / "开发总纲-AI24X-API-v3.5-开发目录副本.md"
    if not hist.exists():
        shutil.move(str(dup), str(hist))
        print("archived dup 总纲 from 开发")
    else:
        dup.unlink()
        print("deleted dup 总纲 from 开发")

# 2) Token 联调
moves = [
    ("docs/DEEPSEEK-联调.md", "docs/联调/DeepSeek联调.md"),
    ("docs/L0-硅基流动联调.md", "docs/联调/L0-硅基流动联调.md"),
    ("docs/邮箱验证码-SMTP联调.md", "docs/联调/邮箱验证码-SMTP联调.md"),
    ("docs/TOKEN-PAY-RUNBOOK.md", "docs/联调/TOKEN支付上线清单.md"),
    ("docs/SECURITY.md", "docs/联调/SECURITY安全基线.md"),
    ("docs/AI24X-Token自由规划-1.0.md", "docs/规划/AI24X-Token自由规划-1.0.md"),
    ("docs/AI24X-根项目平台设计方案-1.0.md", "docs/历史/AI24X-根项目平台设计方案-1.0.md"),
    ("docs/站点与子项目规划.md", "docs/规划/站点与子项目规划.md"),
    ("docs/账号注册登录-首期设计.md", "docs/规划/账号注册登录-首期设计.md"),
    ("docs/MVP-测试与联调.md", "docs/联调/MVP-测试与联调.md"),
]

for a, b in moves:
    move(a, b)

# 3) root loose files → docs + stub
root_moves = [
    ("开发总纲-AI24X-API-v3.5.md", "docs/规划/开发总纲-AI24X-API-v3.5.md"),
    ("开发任务-Token聚合MVP.md", "docs/开发/开发任务-Token聚合MVP.md"),
]
for a, b in root_moves:
    s, d = ROOT / a, ROOT / b
    if not s.exists():
        print("skip root missing", a)
        continue
    if d.exists():
        # prefer docs copy; replace root with stub
        s.write_text(
            f"# 已迁移\n\n现行文档：`{b}`\n\n请勿在仓库根目录维护副本。\n",
            encoding="utf-8",
        )
        print("stubbed root", a)
    else:
        shutil.move(str(s), str(d))
        s.write_text(
            f"# 已迁移\n\n现行文档：`{b}`\n",
            encoding="utf-8",
        )
        print("moved root", a)

# 4) archive other known root planning names if present
for name in [
    "开发总纲-AI24X-API-v3.2-科审版.md",
    "开发总纲-AI24X-API-v3.3.md",
    "开发总纲-AI24X-API平台.md",
    "开发总纲-AI24X-API平台-v3.1.md",
    "开发总纲-AI24X-API平台-v3.1-审校版.md",
    "产品规划-Token平台v2.md",
]:
    s = ROOT / name
    if s.exists() and s.stat().st_size > 200:
        d = DOCS / "历史" / name
        if not d.exists():
            shutil.move(str(s), str(d))
            (ROOT / name).write_text(f"# 已归档\n\n见 `docs/历史/{name}`\n", encoding="utf-8")
            print("archived", name)
        else:
            s.write_text(f"# 已归档\n\n见 `docs/历史/{name}`\n", encoding="utf-8")
            print("stubbed archived", name)

print("OK")
