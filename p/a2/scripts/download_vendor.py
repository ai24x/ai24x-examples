from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Source:
    dest: str
    url: str
    sha256: str
    notes: str


def _utc_http_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _sleep_jitter(base_s: float) -> None:
    # 防止固定频率触发风控：给一点随机抖动
    jitter = base_s * (0.25 + random.random() * 0.75)
    time.sleep(jitter)


def _download(
    url: str,
    dest: str,
    *,
    etag: str | None,
    last_modified: str | None,
    timeout_s: float = 20.0,
) -> tuple[bytes | None, dict[str, str], int]:
    headers = {
        "User-Agent": "ai24x-vendor-fetch/1.0",
        "Accept": "*/*",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            data = resp.read()
            return data, resp_headers, status
    except urllib.error.HTTPError as e:
        # 304 Not Modified / 429 Too Many Requests / 403 Forbidden etc.
        resp_headers = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        return None, resp_headers, int(e.code)
    except Exception:
        raise


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sources_path = os.path.join(repo_root, "scripts", "vendor_sources.json")
    state_path = os.path.join(repo_root, "scripts", ".vendor_download_state.json")

    sources_raw = _read_json(sources_path)
    sources: list[Source] = []
    for dest, meta in sources_raw.items():
        sources.append(
            Source(
                dest=str(dest),
                url=str(meta.get("url", "")).strip(),
                sha256=str(meta.get("sha256", "")).strip(),
                notes=str(meta.get("notes", "")).strip(),
            )
        )

    state: dict[str, Any] = {}
    if os.path.exists(state_path):
        try:
            state = _read_json(state_path)
        except Exception:
            state = {}

    # 全局节流：默认低速低并发（单线程），避免触发封禁
    base_delay_s = float(os.getenv("AI24X_VENDOR_DELAY_S", "0.6"))
    max_retries = int(os.getenv("AI24X_VENDOR_RETRIES", "4"))

    ok = 0
    skipped = 0
    failed = 0

    for i, src in enumerate(sources, start=1):
        if not src.url:
            print(f"[{i}/{len(sources)}] SKIP {src.dest} (missing url)")
            skipped += 1
            continue

        abs_dest = os.path.abspath(os.path.join(repo_root, src.dest))
        os.makedirs(os.path.dirname(abs_dest), exist_ok=True)

        st = state.get(src.dest, {}) if isinstance(state.get(src.dest), dict) else {}
        etag = st.get("etag")
        last_modified = st.get("last_modified")

        # 若文件存在且配置了 sha256，则先校验；匹配则跳过网络请求
        if os.path.exists(abs_dest) and src.sha256:
            try:
                if _sha256_file(abs_dest).lower() == src.sha256.lower():
                    print(f"[{i}/{len(sources)}] OK   {src.dest} (sha256 match, no download)")
                    ok += 1
                    continue
            except Exception:
                pass

        # 轻微节流
        if i > 1:
            _sleep_jitter(base_delay_s)

        attempt = 0
        while True:
            attempt += 1
            try:
                data, resp_headers, status = _download(src.url, abs_dest, etag=etag, last_modified=last_modified)
            except Exception as e:
                if attempt <= max_retries:
                    backoff = min(12.0, 0.8 * (2 ** (attempt - 1)))
                    print(f"[{i}/{len(sources)}] RETRY {src.dest} ({type(e).__name__}) in {backoff:.1f}s")
                    time.sleep(backoff)
                    continue
                print(f"[{i}/{len(sources)}] FAIL {src.dest} ({type(e).__name__}: {e})")
                failed += 1
                break

            if status == 304:
                print(f"[{i}/{len(sources)}] OK   {src.dest} (not modified)")
                ok += 1
                break

            if status in (429, 403):
                # 触发风控：直接降速并退避
                retry_after = resp_headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    wait_s = float(retry_after)
                else:
                    wait_s = min(60.0, 5.0 * attempt)
                print(f"[{i}/{len(sources)}] BACKOFF {src.dest} (HTTP {status}) wait {wait_s:.1f}s")
                time.sleep(wait_s)
                if attempt <= max_retries:
                    continue
                print(f"[{i}/{len(sources)}] FAIL {src.dest} (HTTP {status})")
                failed += 1
                break

            if data is None:
                print(f"[{i}/{len(sources)}] FAIL {src.dest} (HTTP {status})")
                failed += 1
                break

            tmp = abs_dest + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, abs_dest)

            etag = resp_headers.get("etag") or etag
            last_modified = resp_headers.get("last-modified") or last_modified
            if not last_modified:
                # 兜底：给一个 If-Modified-Since 值，减少重复拉取
                try:
                    last_modified = _utc_http_date(os.path.getmtime(abs_dest))
                except Exception:
                    pass

            got_sha = ""
            try:
                got_sha = _sha256_file(abs_dest)
            except Exception:
                got_sha = ""

            state[src.dest] = {
                "url": src.url,
                "etag": etag,
                "last_modified": last_modified,
                "sha256": got_sha,
                "fetched_at": int(time.time()),
                "size": len(data),
            }
            _write_json(state_path, state)

            print(f"[{i}/{len(sources)}] OK   {src.dest} ({len(data)} bytes)")
            ok += 1
            break

    print(f"\nDone. ok={ok} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

