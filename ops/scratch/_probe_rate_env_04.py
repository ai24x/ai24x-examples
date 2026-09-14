# -*- coding: utf-8 -*-
import os, re
from pathlib import Path
p = Path(r"C:\ai24x01\api\.env")
text = p.read_text(encoding="utf-8", errors="ignore")
for key in ("CHAT_RATE_PER_MINUTE", "CHAT_RATE_PER_IP_PER_MINUTE", "ENABLE_RATE_LIMITING", "TOKEN_LLM_DEFAULT_MAX_TOKENS"):
    m = re.search(rf"^{re.escape(key)}\s*=\s*(.*)$", text, re.M)
    print(f"{key}={m.group(1).strip() if m else '(unset)'}")
