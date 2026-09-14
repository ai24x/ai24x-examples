# -*- coding: utf-8 -*-
from pathlib import Path
from urllib.parse import urlparse

for line in Path("api/.env").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL=") and not line.lstrip().startswith("#"):
        raw = line.split("=", 1)[1].strip().strip("\"'")
        u = urlparse(raw)
        print("engine=", u.scheme)
        print("host=", u.hostname)
        print("port=", u.port)
        print("database=", (u.path or "").lstrip("/"))
        print("user=", u.username)
        break
else:
    print("DATABASE_URL not found")
