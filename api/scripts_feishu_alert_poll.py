#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预警 → 飞书私信 轮询器（部署在副脑04 云主机等可访问 openclaw.json 的机器，7x24）

流程（每 5 分钟由计划任务触发）：
  1. GET <OPS_ALERT_API>/v1/admin/token/alerts/latest（鉴权 X-Admin-Key / X-SMS-Internal-Key）
  2. last_push_at 变化且非空 → 私信 last_push_text（级别从文本 P0xn 判断；深夜非 P0 静默）
  3. 值班：active_count>0 且距上次私信 >30min → 值班重提醒（深夜非 P0 静默）
  4. 更新本地 last_seen 文件（去重）

配置（环境变量）：
  OPS_ALERT_API       预警接口地址（默认 http://127.0.0.1:8000）
  OPS_ALERT_KEY       管理 key（必填，生产用 SMS_INTERNAL_KEY / ADMIN_API_KEY 值）
  FEISHU_OPENCLAW_JSON  openclaw.json 路径（默认自动探测）
  FEISHU_PM_OPEN_ID    雷总本应用视角 open_id（默认取 openclaw.json allowFrom[0]）

CLI：
  python scripts_feishu_alert_poll.py                # 正常轮询
  python scripts_feishu_alert_poll.py --dry-run      # 只打印不发送
  python scripts_feishu_alert_poll.py --duty-test    # 值班提醒测试（发送·测试·私信）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from feishu_notify import FeishuNotify, _cst_now, _in_silent_hours

_LAST_SEEN_FILE = Path(__file__).resolve().parent / "data" / "feishu_poll_last.txt"
_DUTY_MINUTES = 30  # 值班重提醒间隔
_QUIET_DUTY_CODES = {"sf_free_key_missing", "or_free_key_missing"}  # 配置类：只推状态变化，不参与值班重提醒


def _api_base() -> str:
    return (os.getenv("OPS_ALERT_API") or "http://127.0.0.1:8000").strip().rstrip("/")


def _api_key() -> str:
    return (os.getenv("OPS_ALERT_KEY") or "").strip()


def _read_last_seen() -> str:
    try:
        if _LAST_SEEN_FILE.is_file():
            return _LAST_SEEN_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _write_last_seen(v: str) -> None:
    try:
        _LAST_SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_SEEN_FILE.write_text(v + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[feishu_alert_poll] last_seen 写入失败: {e}", flush=True)


def _fetch_latest(dry_run: bool = False) -> Optional[dict]:
    key = _api_key()
    if not key:
        print("[feishu_alert_poll] OPS_ALERT_KEY 未配置，跳过", flush=True)
        return None
    import httpx

    url = _api_base() + "/v1/admin/token/alerts/latest"
    try:
        r = httpx.get(
            url,
            headers={"X-SMS-Internal-Key": key, "X-Admin-Key": key},
            timeout=15,
        )
        data = r.json()
    except Exception as e:
        print(f"[feishu_alert_poll] 拉取预警失败: {e}", flush=True)
        return None
    if isinstance(data, dict) and data.get("ok") is True:
        return data
    print(f"[feishu_alert_poll] 接口异常: {json.dumps(data, ensure_ascii=False)[:200]}", flush=True)
    return None


def _fetch_live(dry_run: bool = False) -> Optional[dict]:
    """实时聚合预警（不推送、不改状态）；last_push_at 为空时兜底私信用。"""
    key = _api_key()
    if not key:
        return None
    import httpx

    url = _api_base() + "/v1/admin/token/alerts/live"
    try:
        r = httpx.get(
            url,
            headers={"X-SMS-Internal-Key": key, "X-Admin-Key": key},
            timeout=15,
        )
        data = r.json()
    except Exception as e:
        print(f"[feishu_alert_poll] 拉取实时预警失败: {e}", flush=True)
        return None
    if isinstance(data, dict) and data.get("ok") is True:
        return data
    print(f"[feishu_alert_poll] 实时接口异常: {json.dumps(data, ensure_ascii=False)[:200]}", flush=True)
    return None


def _level_from_text(text: str) -> str:
    m = re.search(r"P0[×x](\d+)", text or "")
    if m and int(m.group(1)) > 0:
        return "error"
    return "warn"


def _run(dry_run: bool = False) -> int:
    fn = FeishuNotify()
    data = _fetch_latest(dry_run=dry_run)
    if not data:
        return 1

    last_push_at = str(data.get("last_push_at") or "").strip()
    push_text = str(data.get("last_push_text") or "").strip()
    active_codes = data.get("active_codes") or []
    active_count = int(data.get("active_count") or 0)
    prev_seen = _read_last_seen()

    # 1) 新推送 → 私信（code 用 last_push_at 唯一标识，天然去重）
    if last_push_at and last_push_at != prev_seen and push_text:
        level = _level_from_text(push_text)
        print(f"[feishu_alert_poll] 新预警推送: {last_push_at} level={level}", flush=True)
        if dry_run:
            print("[dry-run] 将私信:", push_text[:120].replace("\n", " "), flush=True)
        else:
            r = fn.send_pm(push_text, code="push:" + last_push_at, level=level)
            print("[feishu_alert_poll] 私信结果:", json.dumps(r, ensure_ascii=False), flush=True)
            _write_last_seen(last_push_at)
        return 0

    # 1b) 兜底：last_push_at 为空（巡检定时任务未注册 / 重置后未巡检）→ 直接私信实时 P0/P1
    if not last_push_at:
        live = _fetch_live(dry_run=dry_run)
        if live:
            act = [a for a in (live.get("alerts") or []) if str(a.get("level")) in ("error", "warn")]
            if act:
                now = _cst_now()
                n_err = sum(1 for a in act if str(a.get("level")) == "error")
                lines = [
                    f"[AI24X 预警·实时] {now.strftime('%m-%d %H:%M')} (CST)",
                    f"当前：P0×{n_err} P1×{len(act) - n_err} · 健康 {live.get('health', {}).get('status', 'unknown')}",
                ]
                for a in act:
                    lines.append(f"{'P0' if str(a.get('level')) == 'error' else 'P1'} {a.get('code')}：{a.get('msg')}")
                text = "\n".join(lines)
                key = "live:" + hashlib.md5(text.encode("utf-8")).hexdigest()[:16]
                if key != prev_seen:
                    print(f"[feishu_alert_poll] 兜底实时预警: {key}", flush=True)
                    if dry_run:
                        print("[dry-run] 将私信:", text[:120].replace("\n", " "), flush=True)
                    else:
                        r = fn.send_pm(text, code=key, level="error" if n_err > 0 else "warn")
                        print("[feishu_alert_poll] 私信结果:", json.dumps(r, ensure_ascii=False), flush=True)
                        _write_last_seen(key)
                    return 0

    # 2) 值班重提醒：仍有未恢复预警且距上次私信 >30min（配置类不重复值班提醒，只推状态变化）
    remind_codes = [c for c in (active_codes or []) if c not in _QUIET_DUTY_CODES]
    if remind_codes and last_push_at:
        last_ts = 0.0
        try:
            last_ts = datetime.fromisoformat(last_push_at).timestamp()
        except Exception:
            last_ts = 0.0
        if last_ts and (time.time() - last_ts) > _DUTY_MINUTES * 60:
            text = f"[AI24X 预警值班] 仍在告警中：{', '.join(remind_codes)}（{len(remind_codes)} 项），请跟进"
            print("[feishu_alert_poll] 值班重提醒", flush=True)
            if dry_run:
                print("[dry-run] 将私信:", text, flush=True)
            else:
                r = fn.duty_remind(text, level="warn")
                print("[feishu_alert_poll] 值班结果:", json.dumps(r, ensure_ascii=False), flush=True)
            _write_last_seen(last_push_at)
            return 0

    print("[feishu_alert_poll] no action (no new push, active=%d)" % active_count, flush=True)
    return 0


def _main() -> int:
    ap = argparse.ArgumentParser(description="预警→飞书私信轮询器")
    ap.add_argument("--dry-run", action="store_true", help="只打印不发送")
    ap.add_argument("--duty-test", action="store_true", help="值班提醒测试（发送·测试·私信）")
    args = ap.parse_args()

    if args.duty_test:
        fn = FeishuNotify()
        r = fn.duty_remind("【值班提醒·测试·】仍在告警中：TEST（模拟，可忽略）", force=True)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        return 0 if r.get("ok") else 1

    return _run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(_main())
