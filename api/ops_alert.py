#!/usr/bin/env python3
"""
运维预警 L1：定时巡检 + 分级飞书推送。

职责：
- 汇总 admin_ops_alerts（上游密钥缺失 / 待履约积压 / VIP 点名降级等）
- 健康探针（GET <base_url>/health）
- 支付通道就绪检查（token_pay_service.public_plans）
- 今日订单 / 近 24h 支付失败统计
- 分级：error→P0 / warn→P1 / info→默认不推（可开 push_info）
- 去抖：同一 code 在冷却窗口内只推一次；恢复时发「已恢复」
- 推送：飞书机器人 Webhook（文本消息），失败不影响主流程

配置优先级：api/data/ops_alert_config.json < 环境变量
  - FEISHU_WEBHOOK_URL          飞书机器人 webhook（最高优先）
  - OPS_ALERT_BASE_URL          健康探针地址（默认 http://127.0.0.1:8000）
  - OPS_ALERT_ENABLED           总开关（默认 1）
  - OPS_ALERT_COOLDOWN_MINUTES  去抖冷却分钟（默认 60）
  - OPS_ALERT_PUSH_INFO         是否推送 info 级（默认 0）

用法（api/ 目录）：
  python scripts_ops_alert.py            # 巡检 + 推送
  python scripts_ops_alert.py --dry-run  # 只打印，不推送
  python scripts_ops_alert.py --reset    # 清空去抖状态

定时建议：
  Windows 计划任务：scripts/register_ops_alert_cron.ps1（每 15 分钟）
  Linux crontab：*/15 * * * * cd /path/to/api && python scripts_ops_alert.py >> logs/ops_alert.log 2>&1

通道：飞书（主）＋邮箱 SMTP（P0/P1，复用 SMTP 配置）＋106 短信（仅 P0，复用 SMS_106 配置）。
      短信国际成本高/不稳定，仅 P0 兜底；收件人见配置 alert_email / sms_mobiles。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "ops_alert_config.json"
_STATE_PATH = Path(__file__).resolve().parent / "data" / "ops_alert_state.json"

_DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "webhook_url": "",
    "cooldown_minutes": 60,
    "push_info": False,
    "base_url": "http://127.0.0.1:8000",
    "sms_enabled": False,
    "sms_channel": "",
    "email_enabled": False,
    "alert_email": "",
    "sms_mobiles": "",
}

_LEVEL_ICON = {"error": "P0", "warn": "P1", "info": "INFO"}

_ALERT_LABELS = {
    "ops_alerts_collect_fail": "告警采集异常",
    "ops_health_down": "服务健康检查失败",
    "pay_no_channel_ready": "支付通道全部未就绪",
    "pay_paypal_not_configured": "PayPal 商户未配置",
    "pay_paypal_not_ready": "PayPal 通道未就绪",
    "pay_status_collect_fail": "支付状态采集异常",
    "pay_failed_spike": "支付失败激增",
    "pay_failed": "支付失败",
    "pay_order_stats_fail": "订单统计异常",
    "upstream_health_collect_fail": "上游健康采集异常",
    "upstream_fail": "上游通道故障",
    "upstream_circuit": "上游熔断触发",
    "price_monitor_fail": "价格监控采集异常",
    "price_alarm": "价格红线（倒挂）",
    "price_warn": "价格预警（低毛利）",
    "pay_pending_backlog": "待履约订单积压",
    "pay_pending": "待履约订单",
    "llm_l1_no_key": "L1 主档未配置密钥",
    "llm_l0_no_key": "L0 备用未配置密钥",
    "or_free_key_missing": "免费池 OpenRouter 密钥缺失",
    "sf_free_key_missing": "免费池硅基密钥缺失",
    "sf_no_key": "硅基主 Key 未配置",
    "vip_degraded": "VIP 点名降级",
    "user_high_burn": "用户消耗异常偏高",
    "intl_vip_burn": "国际 VIP 消耗异常",
}


def _alert_label(code: str) -> str:
    c = str(code or "")
    for prefix, label in (
        ("price_warn_", "价格预警（低毛利）"),
        ("price_alarm_", "价格红线（倒挂）"),
        ("upstream_fail_", "上游通道故障"),
        ("upstream_circuit_", "上游熔断触发"),
    ):
        if c.startswith(prefix):
            return label
    return _ALERT_LABELS.get(c, c)

_LEVEL_RANK = {"info": 0, "warn": 1, "error": 2}


def _cst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


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
        print(f"[ops_alert] 写入失败: {e}", flush=True)


def load_config() -> dict[str, Any]:
    cfg = dict(_DEFAULT_CONFIG)
    cfg.update(_load_json(_CONFIG_PATH, {}) or {})
    env_url = (os.getenv("FEISHU_WEBHOOK_URL") or "").strip()
    if env_url:
        cfg["webhook_url"] = env_url
    cfg["base_url"] = (
        (os.getenv("OPS_ALERT_BASE_URL") or cfg.get("base_url") or "").strip()
        or "http://127.0.0.1:8000"
    )
    try:
        cfg["enabled"] = bool(int(os.getenv("OPS_ALERT_ENABLED", "1")))
    except ValueError:
        cfg["enabled"] = True
    try:
        cfg["cooldown_minutes"] = max(
            1, int(os.getenv("OPS_ALERT_COOLDOWN_MINUTES", str(cfg.get("cooldown_minutes") or 60)))
        )
    except ValueError:
        cfg["cooldown_minutes"] = 60
    try:
        cfg["push_info"] = bool(int(os.getenv("OPS_ALERT_PUSH_INFO", "0")))
    except ValueError:
        cfg["push_info"] = False
    return cfg


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    """合并保存配置；webhook_url 传空字符串=清除（回退 env）。"""
    cur = load_config()
    for key in (
        "enabled",
        "webhook_url",
        "cooldown_minutes",
        "push_info",
        "base_url",
        "sms_enabled",
        "sms_channel",
        "email_enabled",
        "alert_email",
        "sms_mobiles",
    ):
        if key in updates and updates[key] is not None:
            cur[key] = updates[key]
    cur["enabled"] = bool(cur.get("enabled"))
    cur["push_info"] = bool(cur.get("push_info"))
    cur["sms_enabled"] = bool(cur.get("sms_enabled"))
    try:
        cur["cooldown_minutes"] = max(1, int(cur.get("cooldown_minutes") or 60))
    except (TypeError, ValueError):
        cur["cooldown_minutes"] = 60
    cur["webhook_url"] = str(cur.get("webhook_url") or "").strip()
    cur["base_url"] = str(cur.get("base_url") or "").strip() or "http://127.0.0.1:8000"
    cur["sms_channel"] = str(cur.get("sms_channel") or "").strip()
    cur["email_enabled"] = bool(cur.get("alert_email"))
    cur["alert_email"] = str(cur.get("alert_email") or "").strip()
    cur["sms_mobiles"] = str(cur.get("sms_mobiles") or "").strip()
    env_url = (os.getenv("FEISHU_WEBHOOK_URL") or "").strip()
    if env_url:
        cur["webhook_url"] = env_url
    _save_json(_CONFIG_PATH, cur)
    return cur


def public_config() -> dict[str, Any]:
    """对外（管理台）展示：webhook 脱敏，不返回完整 URL。"""
    cfg = load_config()
    url = cfg.get("webhook_url") or ""
    st = load_state()
    codes = st.get("codes") or {}
    active = sorted(k for k, v in codes.items() if v.get("active"))
    return {
        "ok": True,
        "enabled": bool(cfg.get("enabled")),
        "webhook_set": bool(url),
        "webhook_tail": url[-8:] if url else "",
        "webhook_from_env": bool((os.getenv("FEISHU_WEBHOOK_URL") or "").strip()),
        "cooldown_minutes": int(cfg.get("cooldown_minutes") or 60),
        "push_info": bool(cfg.get("push_info")),
        "base_url": cfg.get("base_url"),
        "sms_enabled": bool(cfg.get("sms_enabled")),
        "sms_channel": cfg.get("sms_channel") or "",
        "email_enabled": bool(cfg.get("email_enabled")),
        "alert_email": cfg.get("alert_email") or "",
        "sms_mobiles": cfg.get("sms_mobiles") or "",
        "active_codes": active,
        "last_check": st.get("last_check") or "",
        "last_push_at": st.get("last_push_at") or "",
        "last_push_text": st.get("last_push_text") or "",
    }


def load_state() -> dict[str, Any]:
    st = _load_json(_STATE_PATH, {}) or {}
    if not isinstance(st, dict) or "codes" not in st:
        st = {"codes": {}}
    return st


def load_state_active_codes() -> list[str]:
    st = load_state()
    return sorted(k for k, v in (st.get("codes") or {}).items() if v.get("active"))


def reset_state() -> None:
    _save_json(_STATE_PATH, {"codes": {}, "reset_at": _cst_now().isoformat()})


def collect_alerts(db) -> dict[str, Any]:
    """聚合预警：admin_ops_alerts + 健康探针 + 支付通道 + 今日订单/失败。"""
    from admin_ops_service import admin_ops_alerts

    alerts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(level: str, code: str, msg: str) -> None:
        if code in seen:
            return
        seen.add(code)
        alerts.append({"level": level, "code": code, "msg": msg})

    # 1) 现有运维告警规则
    try:
        r = admin_ops_alerts(db)
        for a in r.get("alerts") or []:
            add(str(a.get("level") or "info"), str(a.get("code") or "unknown"), str(a.get("msg") or ""))
    except Exception as e:
        add("error", "ops_alerts_collect_fail", f"告警采集异常: {e}")

    # 2) 健康探针
    cfg = load_config()
    health: dict[str, Any] = {"base_url": cfg.get("base_url"), "status": "unknown"}
    try:
        from urllib.parse import urlparse

        _host = (urlparse(cfg.get("base_url") or "").hostname or "").lower()
        if _host in ("127.0.0.1", "localhost", "::1"):
            # 自请求探针会在 API 进程内死锁（async 处理器同步探针阻塞事件循环），本地回环直接视为健康
            health["status"] = "healthy"
            health["http"] = 200
            health["note"] = "loopback self, skip http probe"
        else:
            import httpx

            h = httpx.get(cfg["base_url"] + "/health", timeout=6.0)
            j = {}
            try:
                j = h.json()
            except Exception:
                pass
            health["status"] = str(j.get("status") or ("down" if h.status_code >= 400 else "unknown"))
            health["http"] = h.status_code
    except Exception as e:
        health["status"] = "down"
        health["error"] = str(e)[:160]
    if health["status"] != "healthy":
        add(
            "error",
            "ops_health_down",
            f"健康探针异常: {health.get('status')} {health.get('http', '')} {health.get('error', '')}".strip(),
        )

    # 3) 支付通道就绪
    try:
        from token_pay_service import public_plans

        pay = public_plans().get("pay") or {}
        enabled = bool(pay.get("enabled"))
        ready = [k for k in ("wechat_ready", "alipay_ready", "paypal_ready") if pay.get(k)]
        health["pay_enabled"] = enabled
        health["pay_ready"] = ready
        if enabled and not ready:
            add("error", "pay_no_channel_ready", "支付已开但微信/支付宝/PayPal 均未就绪")
        if enabled and not pay.get("paypal_configured"):
            add("warn", "pay_paypal_not_configured", "PayPal 商户未配置（国际站收银不可用）")
        if enabled and not pay.get("paypal_ready"):
            add("warn", "pay_paypal_not_ready", "PayPal 通道未就绪（缺 Key 或 sandbox/live 未配齐）")
    except Exception as e:
        add("warn", "pay_status_collect_fail", f"支付状态采集异常: {e}")

    # 4) 今日订单 / 近 24h 失败
    try:
        from sqlalchemy import func

        from models import TokenPayOrder

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = (
            db.query(
                func.count(TokenPayOrder.id),
                func.coalesce(func.sum(TokenPayOrder.amount_usd), 0),
            )
            .filter(TokenPayOrder.created_at >= day_start, TokenPayOrder.status == "paid")
            .first()
        )
        from token_pay_service import pending_order_expired

        _pend_rows = (
            db.query(TokenPayOrder).filter(TokenPayOrder.status == "pending").all()
        )
        pending = len(
            [x for x in _pend_rows if not pending_order_expired(x) and not getattr(x, "confirmed_unpaid_at", None)]
        )
        pending_expired = len([x for x in _pend_rows if pending_order_expired(x)])
        kept_reconcile = len(
            [
                x
                for x in _pend_rows
                if pending_order_expired(x) and getattr(x, "transaction_id", None) and not getattr(x, "confirmed_unpaid_at", None)
            ]
        )
        confirmed_unpaid = len([x for x in _pend_rows if getattr(x, "confirmed_unpaid_at", None)])
        failed_24h = int(
            db.query(func.count(TokenPayOrder.id))
            .filter(TokenPayOrder.status == "failed", TokenPayOrder.created_at >= now - timedelta(hours=24))
            .scalar()
            or 0
        )
        health["today_paid"] = int(today[0] or 0) if today else 0
        health["today_usd_cents"] = int(today[1] or 0) if today else 0
        health["pending"] = pending
        health["pending_expired"] = pending_expired
        health["kept_reconcile"] = kept_reconcile
        health["confirmed_unpaid"] = confirmed_unpaid
        health["failed_24h"] = failed_24h
        if failed_24h >= 3:
            add("warn", "pay_failed_spike", f"近 24h 支付失败 {failed_24h} 笔，请核查通道")
        elif failed_24h > 0:
            add("info", "pay_failed", f"近 24h 支付失败 {failed_24h} 笔")
    except Exception as e:
        add("warn", "pay_order_stats_fail", f"订单统计异常: {e}")

    # 5) 上游通道健康（窗口失败率 / 模型连续失败 / 熔断状态）
    try:
        from upstream_health import snapshot as _uh_snapshot

        uh = _uh_snapshot()
        now_ts = int(time.time())
        win_s = int(uh.get("window_s") or 600)
        for pid, st in (uh.get("recs") or {}).items():
            w = st.get("window") or {}
            w_total = int(w.get("total") or 0)
            w_fail = int(w.get("fail") or 0)
            # 仅统计窗口未过期（近期确有请求）时的失败率，避免修复后不再请求的历史残留永久告警
            if (now_ts - int(w.get("start") or 0)) <= win_s and w_total >= 5 and w_fail / max(1, w_total) >= 0.6:
                rate = round(w_fail * 100.0 / max(1, w_total))
                add(
                    "error",
                    f"upstream_fail_{pid}",
                    f"上游通道 {pid} 近 10 分钟失败率 {rate}%（{w_fail}/{w_total}），连续失败 {st.get('consec')} 次",
                )
            for mid, m in (st.get("models") or {}).items():
                # 连续失败告警同样要求最近窗口内有该模型活动，历史 stale 计数不再告警
                if (now_ts - int(m.get("last_ts") or 0)) <= win_s and int(m.get("consec") or 0) >= 3:
                    safe_mid = "".join(c if c.isalnum() else "_" for c in str(mid))
                    add(
                        "warn",
                        f"upstream_model_fail_{pid}_{safe_mid[:48]}",
                        f"模型 {mid} 经 {pid} 连续失败 {m.get('consec')} 次，点名易降级",
                    )
        for pid2, s2 in (uh.get("circuit") or {}).items():
            if s2.get("open"):
                add(
                    "error",
                    f"upstream_circuit_{pid2}",
                    f"通道 {pid2} 已自动熔断（{s2.get('reason') or '连续失败'}），冷却至 {s2.get('until_cst')}",
                )
    except Exception as e:
        add("warn", "upstream_health_collect_fail", f"上游健康采集异常: {e}")


    # 6) 价格与毛利监控（倒挂 / 低毛利 / 成本高于市场最低）
    try:
        from price_monitor import snapshot as _pm_snapshot

        pm = _pm_snapshot()
        for r in (pm.get("rows") or []):
            rid = "".join(c if c.isalnum() else "_" for c in str(r.get("id") or ""))[:40]
            if r.get("level") == "alarm":
                add(
                    "error",
                    f"price_alarm_{rid}",
                    f"价格红线: {r.get('title')} GM_in={r.get('gm_in')}% GM_out={r.get('gm_out')}% "
                    f"混合={r.get('gm_blend')}% ({'; '.join(r.get('flags') or [])})",
                )
            elif r.get("level") == "warn":
                add(
                    "warn",
                    f"price_warn_{rid}",
                    f"价格预警: {r.get('title')} 混合毛利={r.get('gm_blend')}% "
                    f"({'; '.join(r.get('flags') or [])})",
                )
    except Exception as e:
        add("warn", "price_monitor_fail", f"价格监控采集异常: {e}")

    return {"ok": True, "alerts": alerts, "health": health}


def _push_feishu(cfg: dict[str, Any], text: str) -> bool:
    url = (cfg.get("webhook_url") or "").strip()
    if not url:
        # 2026-08-14: 未配自定义机器人 webhook 时，回退 04 应用群推送
        # （feishu_notify 自动探测 openclaw.json，与部署回执同通道，夜间群发不受限）
        try:
            import subprocess
            import sys

            r = subprocess.run(
                [sys.executable, "feishu_notify.py", "--group", text],
                cwd=Path(__file__).resolve().parent,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode == 0:
                print("[ops_alert] feishu 回退 04 应用群推送成功", flush=True)
                return True
            print(
                f"[ops_alert] feishu 回退失败 rc={r.returncode}: "
                f"{str(r.stdout or '')[-300:]} {str(r.stderr or '')[-300:]}",
                flush=True,
            )
            return False
        except Exception as e:
            print(f"[ops_alert] feishu 回退异常: {e}", flush=True)
            return False
    try:
        import httpx

        r = httpx.post(url, json={"msg_type": "text", "content": {"text": text}}, timeout=10.0)
        if r.status_code >= 400:
            print(f"[ops_alert] feishu HTTP {r.status_code}: {r.text[:200]}", flush=True)
            return False
        print("[ops_alert] feishu ok", flush=True)
        return True
    except Exception as e:
        print(f"[ops_alert] feishu skipped: {e}", flush=True)
        return False




def _push_email(cfg: dict[str, Any], text: str) -> bool:
    """SMTP 邮件通道（复用 config.settings.smtp_*；收件人 alert_email 逗号分隔）。"""
    to_list = [x.strip() for x in str(cfg.get("alert_email") or "").split(",") if x.strip()]
    if not to_list:
        print("[ops_alert] alert_email 未配置，跳过邮件", flush=True)
        return False
    try:
        from config import settings
    except Exception as e:
        print("[ops_alert] email config load fail: %s" % e, flush=True)
        return False
    host = (settings.smtp_host or "").strip()
    user = (settings.smtp_user or "").strip()
    password = (settings.smtp_password or "").strip().strip(chr(34)).strip(chr(39))
    from_addr = (settings.smtp_from or user).strip()
    if not (host and user and password and from_addr):
        print("[ops_alert] SMTP 未配置，跳过邮件", flush=True)
        return False
    try:
        import smtplib
        import ssl
        from email.message import EmailMessage
    except Exception as e:
        print("[ops_alert] email import fail: %s" % e, flush=True)
        return False
    msg = EmailMessage()
    msg["Subject"] = "[AI24X 运维预警] " + _cst_now().strftime("%m-%d %H:%M")
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    msg.set_content(text)
    try:
        port = int(settings.smtp_port or 587)
        if bool(settings.smtp_use_ssl) or port == 465:
            context = ssl.create_default_context()
            ssl_port = 465 if port == 587 and bool(settings.smtp_use_ssl) else port
            with smtplib.SMTP_SSL(host, ssl_port, timeout=20, context=context) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                if bool(settings.smtp_use_tls):
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
        print("[ops_alert] email ok -> %s" % ", ".join(to_list), flush=True)
        return True
    except Exception as e:
        print("[ops_alert] email send fail: %s" % str(e)[:160], flush=True)
        return False


def _push_sms(cfg: dict[str, Any], text: str) -> bool:
    """106 短信通道（仅 P0；复用 SMS_106 配置；收件人 sms_mobiles 逗号分隔）。"""
    mobiles = [x.strip() for x in str(cfg.get("sms_mobiles") or "").split(",") if x.strip()]
    if not mobiles:
        print("[ops_alert] sms_mobiles 未配置，跳过短信", flush=True)
        return False
    try:
        from config import settings
    except Exception as e:
        print("[ops_alert] sms config load fail: %s" % e, flush=True)
        return False
    if not settings.sms_106_enabled:
        print("[ops_alert] SMS_106_ENABLED=false，跳过短信", flush=True)
        return False
    short = (text[:58] + "...") if len(text) > 58 else text
    import asyncio
    from sms_106_client import send_sms_106

    async def _go(mobile: str):
        return await send_sms_106(
            endpoint=settings.sms_106_endpoint,
            account=settings.sms_106_account,
            password=settings.sms_106_password,
            mobile=mobile,
            content=short,
            sign_name=settings.sms_106_sign_name or None,
        )

    ok = True
    loop = asyncio.new_event_loop()
    try:
        for m in mobiles:
            try:
                r = loop.run_until_complete(_go(m))
                if isinstance(r, tuple):
                    one = bool(r[0])
                elif isinstance(r, dict):
                    one = bool(r.get("ok"))
                else:
                    one = bool(r)
                ok = ok and one
                print("[ops_alert] sms %s -> %s" % (m, "ok" if one else "fail"), flush=True)
            except Exception as e:
                ok = False
                print("[ops_alert] sms fail %s: %s" % (m, str(e)[:120]), flush=True)
    finally:
        loop.close()
    return ok


def _fmt_alert(a: dict[str, Any]) -> str:
    icon = _LEVEL_ICON.get(str(a.get("level")), "?")
    return f"{icon} {_alert_label(str(a.get('code')))}：{a.get('msg')}"


def run_check(db, *, push: bool = True, dry_run: bool = False) -> dict[str, Any]:
    """巡检主流程。dry_run=True 时不推送、不改状态。"""
    cfg = load_config()
    if not cfg.get("enabled"):
        return {"ok": True, "skipped": "disabled", "alerts": [], "health": {}}

    collected = collect_alerts(db)
    alerts = collected.get("alerts") or []
    health = collected.get("health") or {}

    alerts.sort(key=lambda a: _LEVEL_RANK.get(str(a.get("level")), 0), reverse=True)
    state = load_state()
    codes_state = state.get("codes") or {}
    now_ts = time.time()
    cooldown = int(cfg.get("cooldown_minutes") or 60) * 60
    push_info = bool(cfg.get("push_info"))

    active_now = {
        str(a.get("code")) for a in alerts if str(a.get("level")) in ("error", "warn") or push_info
    }
    new_push: list[dict[str, Any]] = []
    recovered: list[str] = []

    for a in alerts:
        code = str(a.get("code"))
        level = str(a.get("level"))
        if level == "info" and not push_info:
            codes_state.pop(code, None)
            continue
        prev = codes_state.get(code) or {}
        if prev.get("active"):
            last = float(prev.get("last_sent") or 0)
            if now_ts - last < cooldown:
                continue
        new_push.append(a)
        codes_state[code] = {"level": level, "active": True, "last_sent": now_ts}

    for code, prev in list(codes_state.items()):
        if prev.get("active") and code not in active_now:
            recovered.append(code)
            codes_state[code] = {"level": prev.get("level"), "active": False, "last_sent": now_ts}

    if dry_run or not push:
        return {
            "ok": True,
            "dry_run": bool(dry_run),
            "health": health,
            "alerts": alerts,
            "would_push": new_push,
            "recovered": recovered,
        }

    lines = [f"[AI24X 运维预警] {_cst_now().strftime('%m-%d %H:%M')} (CST)"]
    n_err = sum(1 for a in alerts if a.get("level") == "error")
    n_warn = sum(1 for a in alerts if a.get("level") == "warn")
    n_info = sum(1 for a in alerts if a.get("level") == "info")
    lines.append(f"当前：P0×{n_err} P1×{n_warn} INFO×{n_info} · 健康 {health.get('status')}")
    if new_push:
        lines.append("— 新预警 —")
        for a in new_push:
            lines.append(_fmt_alert(a))
    if recovered:
        lines.append("— 已恢复 —")
        for c in recovered:
            lines.append(f"OK {c}")
    if not new_push and not recovered:
        lines.append("（无变化，冷却中静默）")
    text = "\n".join(lines)

    pushed_feishu = _push_feishu(cfg, text)
    pushed_email = _push_email(cfg, text) if cfg.get("email_enabled") else False
    pushed_sms = _push_sms(cfg, text) if (cfg.get("sms_enabled") and n_err > 0) else False
    pushed = pushed_feishu or pushed_email or pushed_sms

    save_state = {"codes": codes_state, "last_check": _cst_now().isoformat()}
    if new_push or recovered:
        save_state["last_push_at"] = _cst_now().isoformat()
        save_state["last_push_text"] = text
    else:
        save_state["last_push_at"] = state.get("last_push_at") or ""
        save_state["last_push_text"] = state.get("last_push_text") or ""
    _save_json(_STATE_PATH, save_state)

    return {
        "ok": True,
        "pushed": pushed,
        "pushed_feishu": pushed_feishu,
        "pushed_email": pushed_email,
        "pushed_sms": pushed_sms,
        "health": health,
        "alerts": alerts,
        "new_push": new_push,
        "recovered": recovered,
        "text": text,
    }
def latest_alert() -> dict[str, Any]:
    """只读快照：最近一次巡检 + 最近一次推送（供副脑04 轮询私信去重）。"""
    state = load_state()
    codes = state.get("codes") or {}
    active = sorted(k for k, v in codes.items() if v.get("active"))
    return {
        "ok": True,
        "last_check": state.get("last_check") or "",
        "last_push_at": state.get("last_push_at") or "",
        "last_push_text": state.get("last_push_text") or "",
        "active_codes": active,
        "active_count": len(active),
    }
