# -*- coding: utf-8 -*-
"""Batch UX/security polish (no price / no payment product binding / no key rotate)."""
from pathlib import Path
import re

ROOT = Path(r"E:/AI24X/ai24x-website/ai24x01")


def sync_api_helpers():
    www = (ROOT / "web/js/api.js").read_text(encoding="utf-8")
    open_p = ROOT / "p/open/web/js/api.js"
    ot = open_p.read_text(encoding="utf-8")
    if "safeNextUrl" in ot:
        print("open api: already synced")
        return
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
            raise SystemExit("export needle missing in open api.js")
        ot = ot.replace(needle, repl, 1)
    open_p.write_text(ot, encoding="utf-8", newline="\n")
    print("open api: synced")


def patch_file(path: Path, pairs):
    t = path.read_text(encoding="utf-8")
    orig = t
    for a, b in pairs:
        if a not in t:
            print(f"WARN missing in {path.name}: {a[:60]!r}...")
            continue
        t = t.replace(a, b)
    if t != orig:
        path.write_text(t, encoding="utf-8", newline="\n")
        print("patched", path.relative_to(ROOT))
    else:
        print("unchanged", path.relative_to(ROOT))


def main():
    sync_api_helpers()

    # --- auth pages www ---
    patch_file(
        ROOT / "web/login.html",
        [
            (
                '· <a href="console.html">Console</a></p>',
                '· <a href="console.html">Account</a></p>',
            ),
            (
                '<strong>Notice</strong>: Sign-up / sign-in are not open in this environment.',
                "<strong>Notice</strong>: Sign-up / sign-in are temporarily unavailable.",
            ),
        ],
    )
    patch_file(
        ROOT / "web/register.html",
        [
            (
                """    function safeNext() {
      try {
        var n = new URL(location.href).searchParams.get("next");
        if (!n || n.indexOf("http") !== 0) return n || "console.html"; // same-site relative path
        var h = new URL(n).hostname.toLowerCase();
        if (h === "markets.ai24x.com" || h === "127.0.0.1" || h === "localhost") return n;
      } catch (e) {}
      return "console.html";
    }""",
                """    function safeNext() {
      try {
        var n = new URL(location.href).searchParams.get("next");
        return AI24X_API.safeNextUrl(n, "console.html");
      } catch (e) {}
      return "console.html";
    }""",
            ),
            (
                '· <a href="console.html">Console</a></p>',
                '· <a href="console.html">Account</a></p>',
            ),
            (
                '<strong>Notice</strong>: Sign-up / sign-in are not open in this environment.',
                "<strong>Notice</strong>: Sign-up / sign-in are temporarily unavailable.",
            ),
        ],
    )
    patch_file(
        ROOT / "web/forgot.html",
        [
            (
                """    function nextUrl() {
      try {
        var u = new URL(location.href);
        var n = u.searchParams.get("next");
        if (n && n.indexOf("http") !== 0) return n;
      } catch (e) {}
      return "console.html";
    }""",
                """    function nextUrl() {
      try {
        var u = new URL(location.href);
        var n = u.searchParams.get("next");
        if (n) return AI24X_API.safeNextUrl(n, "console.html");
      } catch (e) {}
      return "console.html";
    }""",
            ),
            (
                '<strong>Notice</strong>: Sign-up / sign-in are not open in this environment.',
                "<strong>Notice</strong>: Sign-up / sign-in are temporarily unavailable.",
            ),
        ],
    )

    # open auth
    for name in ("login.html", "register.html", "forgot.html"):
        p = ROOT / "p/open/web" / name
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        orig = t
        # generic next harden
        t = re.sub(
            r"if \(n && n\.indexOf\(\"http\"\) !== 0\) return n;",
            'if (n) return AI24X_API.safeNextUrl(n, "console.html");',
            t,
        )
        t = re.sub(
            r"if \(n && isSafeNext\(n\)\) return n;",
            'if (n) return AI24X_API.safeNextUrl(n, "console.html");',
            t,
        )
        # remove weak isSafeNext if present
        t = re.sub(
            r"\n\s*function isSafeNext\(url\) \{[\s\S]*?\n\s*\}\n",
            "\n",
            t,
            count=1,
        )
        # safeNext function block variants
        t = t.replace(
            """    function safeNext() {
      try {
        var n = new URL(location.href).searchParams.get("next");
        if (!n || n.indexOf("http") !== 0) return n || "console.html"; // same-site relative path
        var h = new URL(n).hostname.toLowerCase();
        if (h === "markets.ai24x.com" || h === "127.0.0.1" || h === "localhost") return n;
      } catch (e) {}
      return "console.html";
    }""",
            """    function safeNext() {
      try {
        var n = new URL(location.href).searchParams.get("next");
        return AI24X_API.safeNextUrl(n, "console.html");
      } catch (e) {}
      return "console.html";
    }""",
        )
        t = t.replace(">Console</a>", ">Account</a>")
        t = t.replace(
            "Sign-up / sign-in are not open in this environment.",
            "Sign-up / sign-in are temporarily unavailable.",
        )
        # oauth_error XSS
        t = t.replace(
            "box.innerHTML = '<div class=\"alert alert-error\">' + t(\"auth.login.oauthFail\", \"Social sign-in failed: \") + err + '</div>';",
            'AI24X_API.setAlertMessage(box, t("auth.login.oauthFail", "Social sign-in failed: ") + err, false);',
        )
        t = t.replace(
            "box.innerHTML = '<div class=\"alert alert-error\">' + (err.message || t(\"auth.login.fail\", \"Login failed\")) + '</div>';",
            'AI24X_API.setAlertMessage(box, err.message || t("auth.login.fail", "Login failed"), false);',
        )
        if t != orig:
            p.write_text(t, encoding="utf-8", newline="\n")
            print("patched", p.relative_to(ROOT))
        else:
            print("unchanged", p.relative_to(ROOT))

    # register www: escape err.message on catch
    rp = ROOT / "web/register.html"
    rt = rp.read_text(encoding="utf-8")
    rt2 = rt
    # common patterns for err.message innerHTML
    rt2 = re.sub(
        r"box\.innerHTML = '<div class=\"alert alert-error\">' \+ \(err\.message \|\| t\(\"auth\.register\.fail\"[^)]+\)\) \+ '</div>';",
        'AI24X_API.setAlertMessage(box, err.message || t("auth.register.fail", "Sign-up failed"), false);',
        rt2,
    )
    rt2 = re.sub(
        r"box\.innerHTML = '<div class=\"alert alert-error\">' \+ \(err\.message \|\| t\(\"auth\.login\.fail\"[^)]+\)\) \+ '</div>';",
        'AI24X_API.setAlertMessage(box, err.message || t("auth.login.fail", "Login failed"), false);',
        rt2,
    )
    if "oauth_error" in rt2 and "setAlertMessage(box, t(\"auth.login.oauthFail\"" not in rt2:
        rt2 = rt2.replace(
            "box.innerHTML = '<div class=\"alert alert-error\">' + t(\"auth.login.oauthFail\", \"Social sign-in failed: \") + err + '</div>';",
            'AI24X_API.setAlertMessage(box, t("auth.login.oauthFail", "Social sign-in failed: ") + err, false);',
        )
    if rt2 != rt:
        rp.write_text(rt2, encoding="utf-8", newline="\n")
        print("patched register err escape")

    print("auth batch done")


if __name__ == "__main__":
    main()
