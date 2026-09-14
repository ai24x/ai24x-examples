# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"e:\AI24X\ai24x-website\ai24x01\web\console.html")
t = p.read_text(encoding="utf-8")
old = (
    '  <script src="config/locales.js?v=20260731b"></script>\n'
    '  <script src="js/api.js?v=20260731a"></script>\n'
    '  <script src="js/i18n.js?v=20260731a"></script>\n'
    '  <script src="js/shell.js?v=20260731a"></script>\n'
    '  <script src="js/app.js?v=20260421a"></script>\n'
    '  <script src="js/console.js?v=20260731a"></script>'
)
new = (
    '  <script src="config/locales.js?v=20260731c"></script>\n'
    '  <script src="js/api.js?v=20260731a"></script>\n'
    '  <script src="js/invite.js?v=20260731a"></script>\n'
    '  <script src="js/i18n.js?v=20260731a"></script>\n'
    '  <script src="js/shell.js?v=20260731a"></script>\n'
    '  <script src="js/app.js?v=20260421a"></script>\n'
    '  <script src="js/console.js?v=20260731c"></script>'
)
if old not in t:
    raise SystemExit("console script block not found")
p.write_text(t.replace(old, new), encoding="utf-8")
print("console ok")

# register.html
rp = Path(r"e:\AI24X\ai24x-website\ai24x01\web\register.html")
rt = rp.read_text(encoding="utf-8")
rold = (
    '  <script src="config/locales.js?v=20260727b"></script>\n'
    '  <script src="js/api.js?v=20260727b"></script>\n'
    '  <script src="js/i18n.js?v=20260726z"></script>\n'
    '  <script src="js/shell.js?v=20260726z"></script>\n'
    '  <script src="js/app.js?v=20260725a"></script>'
)
rnew = (
    '  <script src="config/locales.js?v=20260731c"></script>\n'
    '  <script src="js/api.js?v=20260731a"></script>\n'
    '  <script src="js/invite.js?v=20260731a"></script>\n'
    '  <script src="js/i18n.js?v=20260731a"></script>\n'
    '  <script src="js/shell.js?v=20260731a"></script>\n'
    '  <script src="js/app.js?v=20260421a"></script>'
)
if rold not in rt:
    raise SystemExit("register script block not found")
rt = rt.replace(rold, rnew)

old_cap = """      // 邀请链接：?invite=CODE 或 ?ref=CODE
      try {
        var qs = new URLSearchParams(window.location.search || "");
        var inv = (qs.get("invite") || qs.get("ref") || qs.get("invite_code") || "").trim();
        var inp = document.getElementById("reg-invite");
        if (inv && inp && !inp.value) inp.value = inv;
      } catch (e) {}"""
new_cap = """      // 邀请跟踪：短链 /r/CODE → ?invite=；也支持 ?ref= / ?i=；并写入 localStorage
      try {
        var inp = document.getElementById("reg-invite");
        if (window.AI24X_INVITE && inp) {
          AI24X_INVITE.applyToInput(inp);
        } else {
          var qs = new URLSearchParams(window.location.search || "");
          var inv = (qs.get("invite") || qs.get("ref") || qs.get("i") || qs.get("invite_code") || "").trim();
          if (inv && inp && !inp.value) inp.value = inv;
        }
      } catch (e) {}"""
if old_cap not in rt:
    raise SystemExit("register capture block not found")
rt = rt.replace(old_cap, new_cap)

# also save invite on submit
old_sub = """      var invite = (document.getElementById("reg-invite").value || "").trim();
      var payload = {
        password: password,
        email: (document.getElementById("reg-email").value || "").trim(),
        email_code: (document.getElementById("reg-email-code").value || "").trim(),
      };
      if (invite) payload.invite_code = invite;"""
new_sub = """      var invite = (document.getElementById("reg-invite").value || "").trim();
      if (window.AI24X_INVITE && invite) AI24X_INVITE.save(invite);
      var payload = {
        password: password,
        email: (document.getElementById("reg-email").value || "").trim(),
        email_code: (document.getElementById("reg-email-code").value || "").trim(),
      };
      if (invite) payload.invite_code = invite;"""
if old_sub not in rt:
    raise SystemExit("register submit block not found")
rt = rt.replace(old_sub, new_sub)
rp.write_text(rt, encoding="utf-8")
print("register ok")
