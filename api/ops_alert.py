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
    "daily_push_limit": 2,
    "push_info": False,
    "base_url": "http://127.0.0.1:8000",
    "sms_enabled": False,
    "sms_channel": "",
    "email_enabled": False,
    "alert_email": "",
    "sms_mobiles": "",
    "balance_alert_enabled": True,
    # 全局兜底阈值；热通道优先用 balance_thresholds
    "balance_threshold_usd": 15,
    "balance_threshold_cny": 40,
    "balance_thresholds": {
        "deepseek": 40,
        "tokenlab": 15,
        "openrouter": 20,
        "requesty": 15,
        "siliconflow_com": 15,
    },
}

# 未设月上限但仍需人工盯控的热通道（免费档 openrouter_free 不算）
_BALANCE_UNMETERED_WATCH = frozenset({"openrouter", "requesty"})
# 无官方余额 API、需人工台账的通道
_BALANCE_MANUAL_WATCH = frozenset({"mimo", "mimo_free", "quickrouter"})

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
    "upstream_balance": "上游通道余额预警",
    "upstream_balance_collect_fail": "余额采集异常",
    "upstream_balance_unmetered": "上游未设额度上限",
    "upstream_balance_manual": "上游需人工盯余额",
    "upstream_balance_fetch": "上游余额接口失败",
    "price_monitor_fail": "价格监控采集异常",
    "price_alarm": "售价盖不住成本",
    "price_warn": "毛利偏低",
    "hero_pending": "建议换主通道",
    "hero_gm_risk": "切通道后请复查毛利",
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
        ("price_warn_", "毛利偏低"),
        ("price_alarm_", "售价盖不住成本"),
        ("hero_pending_", "建议换主通道"),
        ("hero_gm_risk_", "切通道后请复查毛利"),
        ("upstream_fail_", "上游通道故障"),
        ("upstream_circuit_", "上游熔断触发"),
        ("upstream_balance_unmetered_", "上游未设额度上限"),
        ("upstream_balance_manual_", "上游需人工盯余额"),
        ("upstream_balance_fetch_", "上游余额接口失败"),
        ("upstream_balance_", "上游通道余额预警"),
    ):
        if c.startswith(prefix):
            return label
    return _ALERT_LABELS.get(c, c)


def _is_balance_priority_code(code: str) -> bool:
    """余额相关告警：P0 必达，不受每日推送限额挤掉。"""
    c = str(code or "")
    return c == "upstream_balance_collect_fail" or c.startswith("upstream_balance_")


def _human_price_msg(row: dict[str, Any]) -> str:
    """管理台可读：说清问题 + 下一步，不堆 GM_in / 内部 code。"""
    title = str(row.get("title") or row.get("id") or "模型")
    rid = str(row.get("id") or "")
    flags = [str(x) for x in (row.get("flags") or [])]
    flag_txt = "；".join(flags)
    cs = str(row.get("cost_source") or "")
    try:
        gm_b = float(row["gm_blend"]) if row.get("gm_blend") is not None else None
    except (TypeError, ValueError):
        gm_b = None
    try:
        gm_o = float(row["gm_out"]) if row.get("gm_out") is not None else None
    except (TypeError, ValueError):
        gm_o = None

    lane = ""
    try:
        from system_flags import effective_l1_lane

        lane = str(effective_l1_lane() or "")
    except Exception:
        lane = ""
    if not lane and cs.startswith("flash_lane:"):
        lane = cs.split(":")[1] if ":" in cs else ""

    action = "请到「供应链」核对成本与售价。"
    if (
        rid.startswith("ds-v4")
        or str(row.get("role") or "") == "default_flash"
        or "deepseek" in title.lower()
    ):
        if lane == "deepseek_official" or "official" in cs:
            action = (
                "Flash 正走 DeepSeek 官方价，输出端易打穿现价。建议改「DeepSeek · OpenRouter」"
                "（看实价），或提高 Flash 售价；点名 DeepSeek 请用 VIP 档。"
            )
        elif lane == "or_deepseek" or "or_deepseek" in cs:
            action = (
                "已按 OpenRouter DeepSeek 实采计价仍亏：可换 MiMo，或提高 Flash 售价。"
                "勿与官网标价混淆。"
            )
        elif lane in ("mimo_official", "or_mimo"):
            action = "Flash 已是 MiMo；若仍报警请核对 flash 售价倍率或刷新价目。"
        elif "flash_lane" not in cs:
            action = "目录可能仍按官网成本估算；以供应链 Flash 通道实价为准。"
    elif "成本高于" in flag_txt:
        action = "账面成本偏高，可到「供应链」换更便宜主通道并同步成本。"

    if row.get("level") == "alarm":
        if gm_b is not None and gm_b < 0:
            core = f"{title}：卖价盖不住成本（综合毛利约 {gm_b}%）"
        elif gm_o is not None and gm_o < 0:
            core = f"{title}：输出端在亏钱（输出毛利约 {gm_o}%）"
        else:
            core = f"{title}：毛利触及红线"
        return f"{core}。{action}"
    if gm_b is not None:
        return f"{title}：毛利偏低（综合约 {gm_b}%）。{action}"
    return f"{title}：毛利需关注。{action}"


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
        cfg["daily_push_limit"] = max(
            1, int(os.getenv("OPS_ALERT_DAILY_LIMIT", str(cfg.get("daily_push_limit") or 2)))
        )
    except ValueError:
        cfg["daily_push_limit"] = 2
    try:
        cfg["push_info"] = bool(int(os.getenv("OPS_ALERT_PUSH_INFO", "0")))
    except ValueError:
        cfg["push_info"] = False
    try:
        cfg["balance_alert_enabled"] = bool(int(os.getenv("OPS_ALERT_BALANCE_ENABLED", str(int(bool(cfg.get("balance_alert_enabled", True)))))))
    except ValueError:
        cfg["balance_alert_enabled"] = True
    try:
        cfg["balance_threshold_usd"] = float(os.getenv("OPS_ALERT_BALANCE_USD", str(cfg.get("balance_threshold_usd") or 15)))
    except ValueError:
        cfg["balance_threshold_usd"] = 15.0
    try:
        cfg["balance_threshold_cny"] = float(os.getenv("OPS_ALERT_BALANCE_CNY", str(cfg.get("balance_threshold_cny") or 40)))
    except ValueError:
        cfg["balance_threshold_cny"] = 40.0
    if not isinstance(cfg.get("balance_thresholds"), dict) or not cfg.get("balance_thresholds"):
        cfg["balance_thresholds"] = dict(_DEFAULT_CONFIG["balance_thresholds"])
    return cfg


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    """合并保存配置；webhook_url 传空字符串=清除（回退 env）。"""
    cur = load_config()
    for key in (
        "enabled",
        "webhook_url",
        "cooldown_minutes",
        "daily_push_limit",
        "push_info",
        "base_url",
        "sms_enabled",
        "sms_channel",
        "email_enabled",
        "alert_email",
        "sms_mobiles",
        "balance_alert_enabled",
        "balance_threshold_usd",
        "balance_threshold_cny",
        "balance_thresholds",
    ):
        if key in updates and updates[key] is not None:
            cur[key] = updates[key]
    cur["enabled"] = bool(cur.get("enabled"))
    cur["push_info"] = bool(cur.get("push_info"))
    cur["balance_alert_enabled"] = bool(cur.get("balance_alert_enabled", True))
    try:
        cur["balance_threshold_usd"] = float(cur.get("balance_threshold_usd") or 15)
    except (TypeError, ValueError):
        cur["balance_threshold_usd"] = 15.0
    try:
        cur["balance_threshold_cny"] = float(cur.get("balance_threshold_cny") or 40)
    except (TypeError, ValueError):
        cur["balance_threshold_cny"] = 40.0
    if not isinstance(cur.get("balance_thresholds"), dict):
        cur["balance_thresholds"] = dict(_DEFAULT_CONFIG["balance_thresholds"])
    # 清洗分通道阈值为 float
    cleaned_th: dict[str, float] = {}
    for k, v in (cur.get("balance_thresholds") or {}).items():
        kid = str(k or "").strip()
        if not kid:
            continue
        try:
            cleaned_th[kid] = float(v)
        except (TypeError, ValueError):
            continue
    cur["balance_thresholds"] = cleaned_th
    cur["sms_enabled"] = bool(cur.get("sms_enabled"))
    try:
        cur["cooldown_minutes"] = max(1, int(cur.get("cooldown_minutes") or 60))
    except (TypeError, ValueError):
        cur["cooldown_minutes"] = 60
    try:
        cur["daily_push_limit"] = max(1, int(cur.get("daily_push_limit") or 2))
    except (TypeError, ValueError):
        cur["daily_push_limit"] = 2
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
        "balance_alert_enabled": bool(cfg.get("balance_alert_enabled", True)),
        "balance_threshold_usd": float(cfg.get("balance_threshold_usd") or 15),
        "balance_threshold_cny": float(cfg.get("balance_threshold_cny") or 40),
        "balance_thresholds": cfg.get("balance_thresholds") or {},
        "daily_push_limit": int(cfg.get("daily_push_limit") or 2),
        "note_balance": "余额跌破阈值为 P0，飞书必达且不受每日推送限额挤掉；未设上限/无接口通道为 P1 提醒。",
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
            # 目录遗留/信息级不进 P0/P1（避免假倒挂刷屏）
            if r.get("stale_default") or r.get("level") == "info":
                continue
            rid = "".join(c if c.isalnum() else "_" for c in str(r.get("id") or ""))[:40]
            if r.get("level") == "alarm":
                add("error", f"price_alarm_{rid}", _human_price_msg(r))
            elif r.get("level") == "warn":
                add("warn", f"price_warn_{rid}", _human_price_msg(r))
        # 主通道：持续建议待确认 + 一键后毛利变差（只告警，不自动切）
        try:
            from price_monitor import list_hero_ops_alerts

            for ha in list_hero_ops_alerts() or []:
                add(
                    str(ha.get("level") or "warn"),
                    str(ha.get("code") or "hero_pending"),
                    str(ha.get("message") or "主通道建议待确认"),
                )
        except Exception as e_hero:
            add("warn", "hero_ops_alert_fail", f"主通道待办采集异常: {e_hero}")
    except Exception as e:
        add("warn", "price_monitor_fail", f"价格监控采集异常: {e}")

    # 7) 上游通道余额预警
    # - 余额低于阈值 → P0（飞书必达，run_check 不受日限额挤掉）
    # - 未设上限 / 无接口 / 采集失败 → P1 可观测提醒（冷却去抖，避免静默漏盯）
    if bool(cfg.get("balance_alert_enabled", True)):
        try:
            from balance_monitor import snapshot as _bal_snapshot

            bal = _bal_snapshot()
            thresholds = cfg.get("balance_thresholds") or {}
            if not isinstance(thresholds, dict):
                thresholds = {}
            usd_th = float(cfg.get("balance_threshold_usd") or 15)
            cny_th = float(cfg.get("balance_threshold_cny") or 40)
            for row in bal.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                if row.get("skip_alert") or row.get("deprecated"):
                    continue
                cid = str(row.get("id") or "").strip()
                if not cid:
                    continue
                title = str(row.get("title") or cid)
                cur = str(row.get("currency") or "").upper()

                # 未设月上限：热通道提醒去控制台设上限，否则永远采不到可预警余额
                if row.get("unmetered") and cid in _BALANCE_UNMETERED_WATCH:
                    add(
                        "warn",
                        f"upstream_balance_unmetered_{cid}",
                        f"{title} 未设月额度上限，无法自动预警余额，请到控制台设上限或人工盯余额",
                    )
                    continue

                # 无官方余额 API：有 key 仍需人工盯
                if row.get("unavailable") and cid in _BALANCE_MANUAL_WATCH:
                    add(
                        "warn",
                        f"upstream_balance_manual_{cid}",
                        f"{title} 无余额接口，请人工盯控制台余额并及时充值",
                    )
                    continue

                # 其它 unavailable（如 TokenLab 缺 mt- key）单独提示
                if row.get("unavailable"):
                    err = str(row.get("error") or "不可查余额")[:80]
                    add(
                        "warn",
                        f"upstream_balance_manual_{cid}",
                        f"{title} 余额不可自动查询：{err}",
                    )
                    continue

                # 采集失败（接口挂了）：可观测，避免当「没余额问题」
                if not row.get("ok"):
                    err = str(row.get("error") or "unknown")[:100]
                    add(
                        "warn",
                        f"upstream_balance_fetch_{cid}",
                        f"{title} 余额接口失败：{err}",
                    )
                    continue

                balv = row.get("balance")
                if balv is None:
                    continue
                th = thresholds.get(cid)
                if th is None:
                    th = usd_th if cur == "USD" else (cny_th if cur == "CNY" else None)
                if th is None:
                    continue
                try:
                    th = float(th)
                    balv = float(balv)
                except (TypeError, ValueError):
                    continue
                if balv < th:
                    add(
                        "error",
                        f"upstream_balance_{cid}",
                        f"{title} 余额 {balv:g} {cur} < 阈值 {th:g} {cur}，请尽快充值",
                    )
        except Exception as e:
            add("error", "upstream_balance_collect_fail", f"余额采集异常: {e}")

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

    # 2026-08-28 Boss order: no change -> silent (no feishu/email/sms), state only
    if not new_push and not recovered:
        save_state = {"codes": codes_state, "last_check": _cst_now().isoformat(),
                      "last_push_at": state.get("last_push_at") or "",
                      "last_push_text": state.get("last_push_text") or "",
                      "last_silent_at": _cst_now().isoformat(),
                      "push_daily": state.get("push_daily") or {}}
        _save_json(_STATE_PATH, save_state)
        return {"ok": True, "pushed": False, "silent": True, "health": health,
                "alerts": alerts, "new_push": [], "recovered": [], "text": text}

    # 2026-08-30 Boss order: 非正常预警每日限频（默认 2 条/天），达限额静默落盘
    # 2026-09-14: 余额相关（upstream_balance_*）不受日限额挤掉，保证充值提醒必达
    daily_limit = max(1, int(cfg.get("daily_push_limit") or 2))
    push_daily = state.get("push_daily") or {}
    today = _cst_now().strftime("%Y-%m-%d")
    if push_daily.get("date") != today:
        push_daily = {"date": today, "count": 0}
    rate_limited = int(push_daily.get("count") or 0) >= daily_limit
    balance_only_bypass = False
    if rate_limited:
        bal_push = [a for a in new_push if _is_balance_priority_code(str(a.get("code") or ""))]
        bal_rec = [c for c in recovered if _is_balance_priority_code(c)]
        if not bal_push and not bal_rec:
            save_state = {"codes": codes_state, "last_check": _cst_now().isoformat(),
                          "last_push_at": state.get("last_push_at") or "",
                          "last_push_text": state.get("last_push_text") or "",
                          "last_silent_at": _cst_now().isoformat(),
                          "push_daily": push_daily}
            _save_json(_STATE_PATH, save_state)
            return {"ok": True, "pushed": False, "rate_limited": True, "health": health,
                    "alerts": alerts, "new_push": new_push, "recovered": recovered, "text": text}
        # 日限额已满：仍推余额相关，并收窄正文避免刷其它噪声
        new_push = bal_push
        recovered = bal_rec
        balance_only_bypass = True
        lines = [f"[AI24X 运维预警] {_cst_now().strftime('%m-%d %H:%M')} (CST) · 余额优先（日限额已满仍推）"]
        lines.append(f"当前：P0×{sum(1 for a in alerts if a.get('level')=='error')} "
                     f"P1×{sum(1 for a in alerts if a.get('level')=='warn')} · 健康 {health.get('status')}")
        if new_push:
            lines.append("— 新预警 —")
            for a in new_push:
                lines.append(_fmt_alert(a))
        if recovered:
            lines.append("— 已恢复 —")
            for c in recovered:
                lines.append(f"OK {c}")
        text = "\n".join(lines)

    pushed_feishu = _push_feishu(cfg, text)
    pushed_email = _push_email(cfg, text) if cfg.get("email_enabled") else False
    # 短信仅 P0；余额优先旁路时按本轮 new_push 是否含 error
    n_err_push = sum(1 for a in new_push if a.get("level") == "error") if balance_only_bypass else n_err
    pushed_sms = _push_sms(cfg, text) if (cfg.get("sms_enabled") and n_err_push > 0) else False
    pushed = pushed_feishu or pushed_email or pushed_sms

    # 余额旁路推送不占用每日普通配额（普通告警仍受限额）
    if not balance_only_bypass:
        push_daily["count"] = int(push_daily.get("count") or 0) + 1
    save_state = {"codes": codes_state, "last_check": _cst_now().isoformat(),
                  "push_daily": push_daily}
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
        "balance_bypass": balance_only_bypass,
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
