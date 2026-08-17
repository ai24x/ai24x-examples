"""Set or replace ?v= on css/js in web/*.html — run after UI changes for remote cache bust."""
from __future__ import annotations

import re
import sys
from pathlib import Path

V = sys.argv[1] if len(sys.argv) > 1 else "20260419"


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    for p in sorted(root.glob("*.html")):
        t = p.read_text(encoding="utf-8")
        orig = t
        t = re.sub(
            r'href="css/base\.css(\?v=[^"]*)?"',
            f'href="css/base.css?v={V}"',
            t,
        )
        t = re.sub(
            r'href="css/themes/theme-blue\.css(\?v=[^"]*)?"',
            f'href="css/themes/theme-blue.css?v={V}"',
            t,
        )
        for name in ("config/locales.js", "js/api.js", "js/i18n.js", "js/shell.js", "js/app.js"):
            t = re.sub(
                rf'src="{re.escape(name)}(\?v=[^"]*)?"',
                f'src="{name}?v={V}"',
                t,
            )
        if t != orig:
            p.write_text(t, encoding="utf-8")
            print("updated", p.name)


if __name__ == "__main__":
    main()
