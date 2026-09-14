import datetime as _dt
import os as _os
from pathlib import Path as _Path


def _repo_root() -> _Path:
    return _Path(_os.getcwd())


def _today_path(root: _Path) -> _Path:
    today = _dt.date.today().isoformat()
    return root / "memory" / "daily" / f"{today}.md"


def _safe_get(d: object, key: str, default=None):
    try:
        if isinstance(d, dict):
            return d.get(key, default)
    except Exception:
        pass
    return default


def _append_line(path: _Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def main() -> None:
    # Cursor docs: subagentStop supports followup_message, but we don't need to return anything.
    root = _repo_root()
    daily = _today_path(root)
    ts = _dt.datetime.now().strftime("%H:%M:%S")

    # Intentionally do NOT read stdin: in some environments stdin is a pipe that never closes.
    # Keep the hook non-blocking and just leave a breadcrumb.
    block = f"\n\n## 子脑完成 {ts}\n\n- （自动记录）subagentStop hook fired\n"

    _append_line(daily, block)


if __name__ == "__main__":
    main()

