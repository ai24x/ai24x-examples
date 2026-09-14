# -*- coding: utf-8 -*-
from pathlib import Path

www = Path(r"E:/AI24X/ai24x-website/ai24x01/web/js/api.js").read_text(encoding="utf-8")
open_p = Path(r"E:/AI24X/ai24x-website/ai24x01/p/open/web/js/api.js")
ot = open_p.read_text(encoding="utf-8")
if "safeNextUrl" in ot:
    print("open already has safeNextUrl")
    raise SystemExit(0)

start = www.index("function isPublicAi24xHost()")
end = www.index("function getApiKey()")
block = www[start:end]

start_o = ot.index("function getBase()")
end_o = ot.index("function getApiKey()")
ot = ot[:start_o] + block + ot[end_o:]

needle = "getBase: getBase,\n    setBase: setBase,"
repl = (
    "getBase: getBase,\n    setBase: setBase,\n"
    "    isPublicAi24xHost: isPublicAi24xHost,\n"
    "    safeNextUrl: safeNextUrl,\n"
    "    setAlertMessage: setAlertMessage,"
)
if "safeNextUrl: safeNextUrl" not in ot:
    if needle not in ot:
        raise SystemExit("export needle missing")
    ot = ot.replace(needle, repl, 1)

open_p.write_text(ot, encoding="utf-8", newline="\n")
print("open api.js synced ok")
