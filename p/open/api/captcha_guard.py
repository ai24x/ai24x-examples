# -*- coding: utf-8 -*-
"""
图形验证码（进程内实现，防批量注册/发码刷子）。

- 纯 Python + Pillow 生成 4 位字符图（轻微仿射扭曲 + 噪点 + 干扰线）
- token -> 答案 存进程内 dict，一次性消费，TTL 5 分钟
- ENABLE_CAPTCHA=0 可整体关闭（回滚兜底）
- 每 IP 5 分钟最多生成 20 张，防图片接口被刷爆
"""
from __future__ import annotations

import base64
import io
import os
import secrets
import threading
import time

# 去除易混淆字符 0/O/1/I/L
_CAPTCHA_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

_store: dict[str, tuple[str, float]] = {}
_ip_window: dict[str, list[float]] = {}
_lock = threading.Lock()
_TTL_S = 300.0
_IP_MAX = 20
_IP_WINDOW_S = 300.0


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def captcha_enabled() -> bool:
    return _env_bool("ENABLE_CAPTCHA", True)


def _random_text(n: int = 4) -> str:
    return "".join(secrets.choice(_CAPTCHA_CHARS) for _ in range(n))


def _render_png(text: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    width, height = 170, 54
    rnd = secrets.SystemRandom()
    image = Image.new("RGB", (width, height), (246, 248, 252))
    draw = ImageDraw.Draw(image)

    # 噪点
    for _ in range(140):
        x = rnd.randrange(width)
        y = rnd.randrange(height)
        c = rnd.randrange(130, 225)
        draw.point((x, y), fill=(c, c, c))
    # 干扰线
    for _ in range(3):
        x1, y1 = rnd.randrange(width), rnd.randrange(height)
        x2, y2 = rnd.randrange(width), rnd.randrange(height)
        draw.line([(x1, y1), (x2, y2)], fill=(rnd.randrange(150, 225), rnd.randrange(150, 225), rnd.randrange(150, 225)), width=1)

    font = None
    for fp in (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(fp, 28)
            break
        except Exception:
            continue

    # 4 个字符，间距 38px，均匀分布，垂直小幅抖动
    for i, ch in enumerate(text):
        x = 28 + i * 38
        y = height // 2 + rnd.randint(-3, 3)
        draw.text((x, y), ch, font=font, fill=(25, 55, 110), anchor="mm")

    image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
    # 轻微仿射扭曲（保持可读）
    image = image.transform(
        (width, height),
        Image.AFFINE,
        (1.0, 0.06, rnd.uniform(-2, 2), 0.0, 1.0, rnd.uniform(-1.5, 1.5)),
        resample=Image.BICUBIC,
    )
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _prune_locked() -> None:
    now = time.time()
    dead = [k for k, (_, exp) in _store.items() if exp < now]
    for k in dead:
        _store.pop(k, None)
    for ip in list(_ip_window):
        _prune_ip_locked(ip)


def _prune_ip_locked(ip: str) -> None:
    now = time.time()
    cut = now - _IP_WINDOW_S
    ts = _ip_window.get(ip)
    if not ts:
        return
    while ts and ts[0] < cut:
        ts.pop(0)
    if not ts:
        _ip_window.pop(ip, None)


def create_captcha(ip: str = "") -> tuple[str, str] | None:
    """返回 (token, data_url_png)；关闭或 Pillow 不可用返回 None。"""
    if not captcha_enabled():
        return None
    now = time.time()
    with _lock:
        _prune_locked()
        if ip and ip != "unknown":
            _prune_ip_locked(ip)
            if len(_ip_window.get(ip, [])) >= _IP_MAX:
                return None
            _ip_window.setdefault(ip, []).append(now)
    try:
        text = _random_text(4)
        png = _render_png(text)
        token = "cap_" + secrets.token_urlsafe(18)
        with _lock:
            _store[token] = (text, now + _TTL_S)
        b64 = base64.b64encode(png).decode("ascii")
        return token, "data:image/png;base64," + b64
    except Exception:
        return None


def verify_captcha(token: str, answer: str, *, bypass_ip: str = "") -> bool:
    """一次性校验。关闭时放行（兼容降级）。

    开发环境本机回环（127.0.0.1 / ::1）请求可免验证码，方便本地冒烟脚本；
    生产环境恒不豁免（is_prod() 为真时直接校验）。
    """
    if not captcha_enabled():
        return True
    if bypass_ip in ("127.0.0.1", "::1", "localhost"):
        try:
            from security_util import is_prod

            if not is_prod():
                return True
        except Exception:
            pass
    if not token or not answer:
        return False
    with _lock:
        tup = _store.pop(token, None)
    if not tup:
        return False
    text, exp = tup
    if time.time() > exp:
        return False
    return (answer or "").strip().upper() == text
