"""
行情官本地身份（P1）：密码哈希与主站 api/auth_user_service 一致（passlib pbkdf2_sha256），
便于按 id 迁入 password_hash 后老用户仍可用同一密码登录。
启用：admin_config.auth_local_enabled = true|1|yes|on
"""

from __future__ import annotations

import logging
from typing import Any

from passlib.context import CryptContext

from . import db
from .sms_local import normalize_mobile, verify_and_consume_otp

logger = logging.getLogger(__name__)

_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bool(_pwd.verify(plain, hashed))
    except Exception:
        return False


def norm_email(email: str) -> str:
    return (email or "").strip().lower()


def register_phone(*, phone: str, password: str, sms_code: str) -> db.User:
    mob = normalize_mobile(phone)
    if len(mob) != 11 or not mob.isdigit():
        raise ValueError("请填写 11 位手机号")
    if not verify_and_consume_otp(mob, "register", sms_code or ""):
        raise ValueError("验证码错误或已过期，请重新获取验证码")
    pw = (password or "").strip()
    if len(pw) < 6:
        raise ValueError("密码至少 6 位")
    existing = db.get_user_auth_by_phone(mob)
    if existing and (existing.password_hash or "").strip():
        raise ValueError("该手机号已注册")
    ph = hash_password(pw)
    if existing:
        db.set_user_password_hash(int(existing.id), ph)
        db.touch_user_contacts(int(existing.id), phone=mob, email=None)
        return db.get_user_auth_by_id(int(existing.id)) or existing
    return db.create_local_user(phone=mob, email=None, password_hash=ph)


def register_email(*, email: str, password: str, email_code: str) -> db.User:
    """邮箱注册：本地模式暂要求已有邮箱 OTP 能力；无主站时仅开发态可用。"""
    em = norm_email(email)
    if not em or "@" not in em:
        raise ValueError("请填写有效邮箱")
    # 本地暂无固定开发码以外的邮箱 OTP（生产应接 SMTP）；与现网行情官以手机为主一致
    raise ValueError("本地身份模式请使用手机号注册")


def login_password(*, phone: str | None, email: str | None, password: str) -> db.User:
    pw = (password or "").strip()
    if not pw:
        raise ValueError("请填写密码")
    u: db.User | None = None
    if phone:
        u = db.get_user_auth_by_phone(normalize_mobile(phone))
    elif email:
        u = db.get_user_auth_by_email(norm_email(email))
    if not u:
        raise ValueError("手机号或密码错误")
    if not (u.password_hash or "").strip():
        raise ValueError("账号尚未设置密码，请使用忘记密码或重新获取验证码完成注册")
    if not verify_password(pw, u.password_hash or ""):
        raise ValueError("手机号或密码错误")
    return u


def change_password(*, user_id: int, old_password: str, new_password: str) -> db.User:
    u = db.get_user_auth_by_id(int(user_id))
    if not u:
        raise ValueError("用户不存在")
    if not (u.password_hash or "").strip() or not verify_password(old_password, u.password_hash or ""):
        raise ValueError("原密码错误")
    np = (new_password or "").strip()
    if len(np) < 6:
        raise ValueError("新密码至少 6 位")
    db.set_user_password_hash(int(user_id), hash_password(np))
    out = db.get_user_auth_by_id(int(user_id))
    if not out:
        raise ValueError("用户不存在")
    return out


def reset_password_phone(*, phone: str, sms_code: str, new_password: str) -> db.User:
    mob = normalize_mobile(phone)
    if len(mob) != 11 or not mob.isdigit():
        raise ValueError("请填写 11 位手机号")
    if not verify_and_consume_otp(mob, "reset", sms_code or ""):
        raise ValueError("验证码错误或已过期，请重新获取验证码")
    u = db.get_user_auth_by_phone(mob)
    if not u:
        raise ValueError("该手机号未注册")
    np = (new_password or "").strip()
    if len(np) < 6:
        raise ValueError("新密码至少 6 位")
    db.set_user_password_hash(int(u.id), hash_password(np))
    out = db.get_user_auth_by_id(int(u.id))
    if not out:
        raise ValueError("该手机号未注册")
    return out


def import_password_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    """
    按主站 auth_users 切片导入：[{id, phone?, email?, password_hash}, ...]
    id 必须与现有配额/订单对齐；只写 password_hash 与联系方式，不删业务数据。
    """
    ok = 0
    skip = 0
    err = 0
    for raw in rows or []:
        try:
            uid = int(raw.get("id") or 0)
            ph = str(raw.get("password_hash") or "").strip()
            if uid <= 0 or not ph:
                skip += 1
                continue
            phone = normalize_mobile(str(raw.get("phone") or "")) or None
            if phone and (len(phone) != 11 or not phone.isdigit()):
                phone = None
            email = norm_email(str(raw.get("email") or "")) or None
            db.upsert_local_auth_user(
                user_id=uid,
                phone=phone,
                email=email,
                password_hash=ph,
            )
            ok += 1
        except Exception as e:
            err += 1
            logger.warning("import auth row failed: %s", e)
    # 导入固定 id 后把自增序列推到 MAX(id)，避免随后注册撞主键
    try:
        db.sync_users_id_sequence()
    except Exception as e:
        logger.warning("sync users id sequence failed: %s", e)
    return {"ok": ok, "skip": skip, "error": err}
