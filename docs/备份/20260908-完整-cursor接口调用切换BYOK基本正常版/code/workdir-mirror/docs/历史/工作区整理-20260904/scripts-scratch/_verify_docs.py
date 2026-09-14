# -*- coding: utf-8 -*-
from pathlib import Path

checks = [
    "docs/规划/开发总纲-AI24X-API-v3.5.md",
    "docs/开发/开发任务-Token聚合MVP.md",
    "docs/决策/Cursor协作流程指南.md",
    "docs/联调/DeepSeek联调.md",
    "docs/联调/邮箱验证码-SMTP联调.md",
    "docs/联调/TOKEN支付上线清单.md",
    "docs/联调/SECURITY安全基线.md",
    "docs/联调/L0-硅基流动联调.md",
    "docs/DEEPSEEK-联调.md",
    "开发总纲-AI24X-API-v3.5.md",
    "docs/规划/AI24X-Token自由规划-1.0.md",
    "docs/规划/站点与子项目规划.md",
]
for p in checks:
    f = Path(p)
    if not f.exists():
        print("MISSING", p)
        continue
    t = f.read_text(encoding="utf-8")
    print(f"{p}\tsize={len(t)}\tstub={'已迁移' in t[:40]}\thead={t[:48].replace(chr(10),' ')}")
