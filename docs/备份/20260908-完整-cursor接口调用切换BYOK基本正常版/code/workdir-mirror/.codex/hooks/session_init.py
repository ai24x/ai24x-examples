import datetime as _dt
import os as _os
from pathlib import Path as _Path


def _repo_root() -> _Path:
    # Hooks run from project root for project hooks.
    return _Path(_os.getcwd())


def _today_path(root: _Path) -> _Path:
    today = _dt.date.today().isoformat()
    return root / "memory" / "daily" / f"{today}.md"


def _read_template(root: _Path) -> str:
    p = root / "memory" / "templates" / "session-ops-card.md"
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _ensure_daily_file(path: _Path, template: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    header = f"# Daily Log {path.stem}\n\n"
    body = template.strip()
    content = header + (body + "\n" if body else "")
    path.write_text(content, encoding="utf-8")


def main() -> None:
    # Cursor docs: sessionStart has no supported output fields. We still do best-effort work.
    # Intentionally do NOT read stdin: in some environments stdin is a pipe that never closes,
    # and reading would block. sessionStart is fire-and-forget anyway.

    root = _repo_root()
    daily = _today_path(root)
    tmpl = _read_template(root)
    _ensure_daily_file(daily, tmpl)


if __name__ == "__main__":
    main()

