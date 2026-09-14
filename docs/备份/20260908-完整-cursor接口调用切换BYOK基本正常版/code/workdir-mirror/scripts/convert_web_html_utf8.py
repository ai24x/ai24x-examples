from __future__ import annotations

from pathlib import Path


def to_utf8_no_bom(p: Path) -> tuple[bool, str]:
    b = p.read_bytes()
    decoders = [
        ("utf-8", "strict"),
        ("utf-8-sig", "strict"),
        # Windows / legacy Chinese encodings commonly decode with GB18030.
        ("gb18030", "strict"),
        # Some files may contain cp1252 smart punctuation mixed in.
        ("cp1252", "strict"),
        # Last resort: preserve bytes without failing (may show � for undecodable).
        ("gb18030", "replace"),
    ]
    s = None
    src = "unknown"
    for enc, errors in decoders:
        try:
            s = b.decode(enc, errors=errors)
            src = f"{enc}:{errors}"
            break
        except UnicodeDecodeError:
            continue
    if s is None:
        # Should never happen, but keep file unchanged if it does.
        return False, "decode_failed"
    nb = s.encode("utf-8")
    if nb == b:
        return False, src
    p.write_bytes(nb)
    return True, src


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "web"
    files = sorted(root.glob("*.html"))
    changed = 0
    for p in files:
        did, src = to_utf8_no_bom(p)
        if did:
            changed += 1
            print(f"converted {p.name} from {src} -> utf-8")
    print(f"done. converted={changed} total={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

