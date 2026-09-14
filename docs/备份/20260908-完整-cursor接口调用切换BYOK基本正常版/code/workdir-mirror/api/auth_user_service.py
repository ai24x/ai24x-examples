from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models import AuthUser
from sms_106_client import normalize_mobile
from sms_otp_memory import verify_and_consume_otp as verify_phone_otp
from email_otp_memory import verify_and_consume_otp as verify_email_otp

# Use PBKDF2 by default to avoid native bcrypt dependency issues on Windows.
# (bcrypt backend may be missing in some environments and would raise at runtime during register/login.)
_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def norm_email(email: str) -> str:
    return (email or "").strip().lower()


def get_by_phone(db: Session, phone: str) -> Optional[AuthUser]:
    p = normalize_mobile(phone)
    if len(p) != 11 or not p.isdigit():
        return None
    return db.query(AuthUser).filter(AuthUser.phone == p).first()


def get_by_email(db: Session, email: str) -> Optional[AuthUser]:
    e = norm_email(email)
    if not e:
        return None
    return db.query(AuthUser).filter(AuthUser.email == e).first()


def create_user_phone(db: Session, phone: str, password: str) -> AuthUser:
    p = normalize_mobile(phone)
    now = datetime.now(timezone.utc)
    u = AuthUser(
        phone=p,
        email=None,
        password_hash=hash_password(password),
        phone_verified_at=now,
        email_verified_at=None,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def create_user_email(db: Session, email: str, password: str) -> AuthUser:
    e = norm_email(email)
    now = datetime.now(timezone.utc)
    u = AuthUser(
        phone=None,
        email=e,
        password_hash=hash_password(password),
        phone_verified_at=None,
        email_verified_at=now,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def authenticate_password(db: Session, *, phone: str | None, email: str | None, password: str) -> Optional[AuthUser]:
    u: Optional[AuthUser] = None
    if phone:
        u = get_by_phone(db, phone)
    elif email:
        u = get_by_email(db, email)
    if not u:
        return None
    if not verify_password(password, u.password_hash):
        return None
    return u


def change_password_for_user(db: Session, user_id: int, old_password: str, new_password: str) -> None:
    u = db.query(AuthUser).filter(AuthUser.id == int(user_id)).first()
    if not u:
        raise ValueError("用户不存在")
    if not verify_password(old_password, u.password_hash):
        raise ValueError("原密码错误")
    np = (new_password or "").strip()
    if len(np) < 6:
        raise ValueError("新密码至少 6 位")
    u.password_hash = hash_password(np)
    db.commit()


def reset_password_phone(db: Session, phone: str, sms_code: str, new_password: str) -> AuthUser:
    mob = normalize_mobile(phone)
    if len(mob) != 11 or not mob.isdigit():
        raise ValueError("手机号格式不正确（需 11 位国内号）")
    if not verify_phone_otp(mob, "reset", sms_code):
        raise ValueError("验证码错误或已过期，请重新获取")
    u = get_by_phone(db, mob)
    if not u:
        raise ValueError("该手机号未注册")
    np = (new_password or "").strip()
    if len(np) < 6:
        raise ValueError("新密码至少 6 位")
    u.password_hash = hash_password(np)
    db.commit()
    db.refresh(u)
    return u


def reset_password_email(db: Session, email: str, email_code: str, new_password: str) -> AuthUser:
    em = norm_email(email)
    if not em or "@" not in em:
        raise ValueError("邮箱格式不正确")
    if not verify_email_otp(em, "reset", email_code):
        raise ValueError("邮箱验证码错误或已过期，请重新获取")
    u = get_by_email(db, em)
    if not u:
        raise ValueError("该邮箱未注册")
    np = (new_password or "").strip()
    if len(np) < 6:
        raise ValueError("新密码至少 6 位")
    u.password_hash = hash_password(np)
    db.commit()
    db.refresh(u)
    return u


def admin_set_password(
    db: Session,
    *,
    user_id: int | None = None,
    phone: str | None = None,
    email: str | None = None,
    new_password: str,
) -> AuthUser:
    """Admin-only force set password without OTP."""
    u: Optional[AuthUser] = None
    if user_id is not None:
        u = db.query(AuthUser).filter(AuthUser.id == int(user_id)).first()
    elif phone:
        u = get_by_phone(db, phone)
    elif email:
        u = get_by_email(db, email)
    if not u:
        raise ValueError("用户不存在")
    np = (new_password or "").strip()
    if len(np) < 6:
        raise ValueError("新密码至少 6 位")
    u.password_hash = hash_password(np)
    db.commit()
    db.refresh(u)
    return u


def admin_set_contact(
    db: Session,
    *,
    user_id: int,
    phone: str | None = None,
    email: str | None = None,
) -> AuthUser:
    """Admin-only force set phone/email binding for an existing user."""
    u = db.query(AuthUser).filter(AuthUser.id == int(user_id)).first()
    if not u:
        raise ValueError("用户不存在")
    p = normalize_mobile(phone) if phone else None
    if p is not None and (len(p) != 11 or not p.isdigit()):
        raise ValueError("手机号格式不正确（需 11 位国内号）")
    e = norm_email(email) if email else None
    if e is not None and ("@" not in e or len(e) < 6):
        raise ValueError("邮箱格式不正确")
    if bool(p) == bool(e):
        raise ValueError("请只填写手机号或邮箱之一")

    # Uniqueness check (friendly errors).
    if p:
        other = db.query(AuthUser).filter(AuthUser.phone == p, AuthUser.id != int(user_id)).first()
        if other:
            raise ValueError("该手机号已被占用")
    if e:
        other = db.query(AuthUser).filter(AuthUser.email == e, AuthUser.id != int(user_id)).first()
        if other:
            raise ValueError("该邮箱已被占用")

    if p:
        u.phone = p
        u.phone_verified_at = datetime.now(timezone.utc)
    if e:
        u.email = e
        u.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return u


def bind_phone_for_user(db: Session, *, user_id: int, phone: str, sms_code: str) -> AuthUser:
    u = db.query(AuthUser).filter(AuthUser.id == int(user_id)).first()
    if not u:
        raise ValueError("用户不存在")
    mob = normalize_mobile(phone)
    if len(mob) != 11 or not mob.isdigit():
        raise ValueError("手机号格式不正确（需 11 位国内号）")
    if not verify_phone_otp(mob, "bind", sms_code):
        raise ValueError("验证码错误或已过期，请重新获取")
    other = db.query(AuthUser).filter(AuthUser.phone == mob, AuthUser.id != int(user_id)).first()
    if other:
        raise ValueError("该手机号已被占用")
    u.phone = mob
    u.phone_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return u


def bind_email_for_user(db: Session, *, user_id: int, email: str, email_code: str) -> AuthUser:
    u = db.query(AuthUser).filter(AuthUser.id == int(user_id)).first()
    if not u:
        raise ValueError("用户不存在")
    em = norm_email(email)
    if not em or "@" not in em:
        raise ValueError("邮箱格式不正确")
    if not verify_email_otp(em, "bind", email_code):
        raise ValueError("验证码错误或已过期，请重新获取")
    other = db.query(AuthUser).filter(AuthUser.email == em, AuthUser.id != int(user_id)).first()
    if other:
        raise ValueError("该邮箱已被占用")
    u.email = em
    u.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(u)
    return u


def is_user_frozen(u: Optional[AuthUser]) -> bool:
    return bool(u is not None and getattr(u, "frozen_at", None))


def auth_user_public_dict(u: AuthUser) -> dict:
    from utm_attribution import acquisition_public_dict

    d = {
        "id": int(u.id),
        "email": u.email or "",
        "phone": u.phone or "",
        "frozen": is_user_frozen(u),
        "frozen_at": u.frozen_at.isoformat() if getattr(u, "frozen_at", None) else None,
        "freeze_reason": (getattr(u, "freeze_reason", None) or "") or None,
    }
    acq = acquisition_public_dict(u)
    if any(acq.get(k) for k in ("utm_source", "utm_campaign", "gclid")):
        d["acquisition"] = acq
    return d


def raise_if_frozen(u: Optional[AuthUser]) -> None:
    """用户可见文案；供登录 / chat / 充值挂点。"""
    from fastapi import HTTPException

    if is_user_frozen(u):
        raise HTTPException(
            status_code=403,
            detail={
                "message_zh": "账号暂不可用，请联系客服。",
                "message_en": "This account is unavailable. Please contact support.",
                "message": "账号暂不可用，请联系客服。",
                "code": "account_frozen",
            },
        )


def set_user_frozen(
    db: Session, *, user_id: int, frozen: bool, reason: str = ""
) -> AuthUser:
    u = db.query(AuthUser).filter(AuthUser.id == int(user_id)).first()
    if not u:
        raise ValueError("用户不存在")
    if frozen:
        u.frozen_at = datetime.now(timezone.utc)
        u.freeze_reason = (reason or "").strip()[:255] or "admin"
    else:
        u.frozen_at = None
        u.freeze_reason = None
    db.commit()
    db.refresh(u)
    return u
