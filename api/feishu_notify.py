#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
feishu-notify：飞书开放平台 API 直连通知公共模块（经验卡：Codex经验卡-飞书通知打通-20260805.md）

原理（三步）：
  1. 凭证：运行时从 openclaw.json 读 channels.feishu.appId/appSecret（绝不硬编码/落盘/打印）
  2. 换 token：POST open.feishu.cn /open-apis/auth/v3/tenant_access_token/internal
  3. 发消息：POST /open-apis/im/v1/messages（私信 open_id / 群发 chat_id，富文本 post，UTF-8）

能力：
  - 私信雷总 / 群发（可 @雷总）
  - 节流：同一 code 默认 6h 合并一次（可覆盖）
  - 深夜策略：CST 23:30-08:30 非 P0(error) 不私信
  - 低资源：无常驻进程，调用即用即退

CLI：
  python feishu_notify.py --config <openclaw.json> --pm "文本" [--code x --level warn] [--force]
  python feishu_notify.py --config <openclaw.json> --group "文本" [--at] [--force]
  python feishu_notify.py --config <openclaw.json> --duty-test [--force]

模块：
  from feishu_notify import FeishuNotify
  fn = FeishuNotify(openclaw_json=..., pm_open_id=..., group_chat_id=...)
  fn.send_pm("文本", code="pay_x", level="warn")
  fn.send_group("文本", at=True)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ---------- 常量 ----------
_DEFAULT_STATE_FILE = Path(__file__).resolve().parent / "data" / "feishu_notify_state.json"
_TOKEN_TTL_SECONDS = 2 * 3600  # tenant_access_token 有效期 2h，缓存内复用
_DEFAULT_THROTTLE_MINUTES = 360  # 同一预警 6h 合并一次
_SILENT_START = (23, 30)  # 深夜静默开始 23:30
_SILENT_END = (8, 30)     # 深夜静默结束 08:30
_API_TOKEN = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_API_MSG = "https://open.feishu.cn/open-apis/im/v1/messages"


def _cst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _in_silent_hours(now: Optional[datetime] = None) -> bool:
    """CST 23:30-08:30 为深夜静默时段。"""
    now = now or _cst_now()
    t = (now.hour, now.minute)
    return t >= _SILENT_START or t < _SILENT_END


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[feishu_notify] 状态写入失败: {e}", flush=True)


def _find_openclaw_json(explicit: Optional[str] = None) -> str:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return str(p)
        raise FileNotFoundError(f"openclaw.json not found: {explicit}")
    env = (os.getenv("FEISHU_OPENCLAW_JSON") or "").strip()
    if env and Path(env).is_file():
        return env
    cands = [
        Path.home() / ".openclaw" / "openclaw.json",
        Path(r"C:\Users\Administrator\.openclaw\openclaw.json"),
        Path(r"C:\Users\Admin\.openclaw\openclaw.json"),
    ]
    for c in cands:
        if c.is_file():
            return str(c)
    raise FileNotFoundError("openclaw.json not found; set FEISHU_OPENCLAW_JSON")


class FeishuNotify:
    def __init__(
        self,
        openclaw_json: Optional[str] = None,
        pm_open_id: Optional[str] = None,
        group_chat_id: Optional[str] = None,
        state_file: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.openclaw_json = _find_openclaw_json(openclaw_json)
        self.pm_open_id = (pm_open_id or os.getenv("FEISHU_PM_OPEN_ID") or "").strip()
        self.group_chat_id = (group_chat_id or os.getenv("FEISHU_GROUP_CHAT_ID") or "").strip()
        self.state_file = Path(state_file or os.getenv("FEISHU_STATE_FILE") or _DEFAULT_STATE_FILE)
        self.timeout = timeout
        self._creds: Optional[dict] = None

    # ---------- 凭证 / token ----------
    def _load_creds(self) -> dict:
        if self._creds:
            return self._creds
        try:
            cfg = json.loads(Path(self.openclaw_json).read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"read openclaw.json failed: {e}")
        f = (cfg.get("channels") or {}).get("feishu") or {}
        app_id = str(f.get("appId") or "").strip()
        app_secret = str(f.get("appSecret") or "").strip()
        if not app_id or not app_secret:
            raise RuntimeError("feishu appId/appSecret missing in openclaw.json")
        if not self.pm_open_id:
            allow = f.get("allowFrom") or []
            if allow:
                self.pm_open_id = str(allow[0]).strip()
        if not self.group_chat_id:
            allow = f.get("groupAllowFrom") or []
            if allow:
                self.group_chat_id = str(allow[0]).strip()
        self._creds = {"app_id": app_id, "app_secret": app_secret}
        return self._creds

    def _get_token(self) -> str:
        """tenant_access_token，2h 文件缓存内复用，降低请求频率。"""
        creds = self._load_creds()
        cache = _load_json(self.state_file, {}) or {}
        tok = cache.get("token") or ""
        exp = float(cache.get("token_exp") or 0)
        if tok and exp > time.time() + 60:
            return tok
        import httpx

        try:
            r = httpx.post(_API_TOKEN, json=creds, timeout=self.timeout)
            data = r.json()
        except Exception as e:
            raise RuntimeError(f"tenant token request failed: {e}")
        code = data.get("code")
        if code is None:
            code = -1
        if int(code) != 0 or not data.get("tenant_access_token"):
            raise RuntimeError(f"tenant token error: code={data.get('code')} msg={data.get('msg')}")
        tok = str(data["tenant_access_token"])
        cache["token"] = tok
        cache["token_exp"] = time.time() + int(data.get("expire", 7200))
        _save_json(self.state_file, cache)
        return tok

    # ---------- 发送 ----------
    @staticmethod
    def _build_post_content(text: str, at_open_id: Optional[str] = None) -> str:
        # 2026-08-14: 多行文本按 \n 拆成 post 段落，避免控制字符进 JSON（此前含换行 → 230001 拒收）
        def esc(s: str) -> str:
            return (
                str(s or "")
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\r", "")
                .replace("\n", " ")
                .replace("\t", " ")
            )

        lines = [esc(ln) for ln in str(text or "").split("\n")]
        if not lines:
            lines = [""]
        if at_open_id:
            inner = ",".join('[{"tag":"text","text":"' + ln + '"}]' for ln in lines)
            inner += '[{"tag":"at","user_id":"' + at_open_id + '","user_name":"Xie Lei"}]'
        else:
            inner = ",".join('[{"tag":"text","text":"' + ln + '"}]' for ln in lines)
        return '{"zh_cn":{"title":"","content":[' + inner + "]}}"

    def send_message(
        self,
        receive_id: str,
        receive_id_type: str,
        text: str,
        at_open_id: Optional[str] = None,
    ) -> bool:
        """发一条消息（post 富文本，UTF-8）。失败抛异常由调用方决定。"""
        self._load_creds()
        if not receive_id:
            raise ValueError("receive_id is empty")
        import httpx

        token = self._get_token()
        content = self._build_post_content(text, at_open_id)
        payload = {"receive_id": receive_id, "msg_type": "post", "content": content}
        r = httpx.post(
            _API_MSG,
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self.timeout,
        )
        data = r.json()
        code = data.get("code")
        if code is None:
            code = -1
        if int(code) != 0:
            raise RuntimeError(f"feishu send fail code={data.get('code')} msg={data.get('msg')}")
        return True

    # ---------- 节流 / 深夜 ----------
    def _throttle(self, code: str, throttle_minutes: int) -> bool:
        """同 code 在窗口内已发过 → True（应跳过）。"""
        if not code:
            return False
        st = _load_json(self.state_file, {}) or {}
        sent = st.get("sent") or {}
        prev = sent.get(code) or {}
        last = float(prev.get("at") or 0)
        if last and (time.time() - last) < throttle_minutes * 60:
            return True
        sent[code] = {"at": time.time(), "at_iso": _cst_now().isoformat()}
        st["sent"] = sent
        _save_json(self.state_file, st)
        return False

    def send_pm(
        self,
        text: str,
        code: Optional[str] = None,
        level: str = "warn",
        force: bool = False,
        throttle_minutes: int = _DEFAULT_THROTTLE_MINUTES,
        silent_policy: bool = True,
    ) -> dict:
        """私信雷总。返回 {ok, skipped, reason}。深夜先于节流检查（深夜跳过不占节流额度）。"""
        try:
            self._load_creds()
            if not self.pm_open_id:
                return {"ok": False, "skipped": True, "reason": "pm_open_id missing"}
            if not force and silent_policy and _in_silent_hours() and level != "error":
                return {"ok": False, "skipped": True, "reason": "silent hours (non-P0)"}
            if not force and code and self._throttle(code, throttle_minutes):
                return {"ok": False, "skipped": True, "reason": f"throttled({code})"}
            self.send_message(self.pm_open_id, "open_id", text)
            return {"ok": True, "skipped": False, "reason": ""}
        except Exception as e:
            return {"ok": False, "skipped": False, "reason": str(e)[:200]}

    def send_group(
        self,
        text: str,
        at: bool = False,
        force: bool = False,
        code: Optional[str] = None,
        throttle_minutes: int = _DEFAULT_THROTTLE_MINUTES,
    ) -> dict:
        """群发（可选 @雷总）。深夜不限制群发。"""
        try:
            self._load_creds()
            if not self.group_chat_id:
                return {"ok": False, "skipped": True, "reason": "group_chat_id missing"}
            if not force and code and self._throttle("group:" + code, throttle_minutes):
                return {"ok": False, "skipped": True, "reason": f"throttled({code})"}
            at_id = self.pm_open_id if at else None
            self.send_message(self.group_chat_id, "chat_id", text, at_open_id=at_id)
            return {"ok": True, "skipped": False, "reason": ""}
        except Exception as e:
            return {"ok": False, "skipped": False, "reason": str(e)[:200]}

    def duty_remind(self, text: str, level: str = "warn", force: bool = False) -> dict:
        """值班重提醒：30min 窗口去重，深夜非 P0 不发。"""
        return self.send_pm(
            text,
            code="duty",
            level=level,
            force=force,
            throttle_minutes=30,
            silent_policy=True,
        )


def _main() -> int:
    ap = argparse.ArgumentParser(description="feishu-notify 飞书直连通知（凭证运行时读 openclaw.json）")
    ap.add_argument("--config", help="openclaw.json 路径（默认自动探测）")
    ap.add_argument("--pm", help="私信雷总文本")
    ap.add_argument("--group", help="群发文本")
    ap.add_argument("--at", action="store_true", help="群发时 @雷总")
    ap.add_argument("--code", help="节流 code（同 code 窗口内合并）")
    ap.add_argument("--level", default="warn", choices=["info", "warn", "error"], help="级别（error=P0）")
    ap.add_argument("--force", action="store_true", help="绕过节流/深夜策略（测试用）")
    ap.add_argument("--duty-test", action="store_true", help="值班提醒测试（标注·测试·）")
    args = ap.parse_args()

    try:
        fn = FeishuNotify(openclaw_json=args.config)
        if args.duty_test:
            r = fn.duty_remind("【值班提醒·测试·】仍在告警中：TEST（模拟，可忽略）", force=args.force)
        elif args.pm:
            r = fn.send_pm(args.pm, code=args.code, level=args.level, force=args.force)
        elif args.group:
            r = fn.send_group(args.group, at=args.at, force=args.force, code=args.code)
        else:
            ap.print_help()
            return 2
    except Exception as e:
        print(json.dumps({"ok": False, "skipped": False, "reason": str(e)[:200]}, ensure_ascii=False), flush=True)
        return 1
    print(json.dumps(r, ensure_ascii=False), flush=True)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_main())
