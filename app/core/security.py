"""
Password hashing and JWT helpers.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

PASSWORD_RESET_PURPOSE = "password_reset"
PASSWORD_RESET_EXPIRE_MINUTES = 30

EMAIL_VERIFICATION_PURPOSE = "email_verification"
EMAIL_VERIFICATION_EXPIRE_HOURS = 24


def hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def create_password_reset_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    payload = {"sub": user_id, "purpose": PASSWORD_RESET_PURPOSE, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def verify_password_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != PASSWORD_RESET_PURPOSE:
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def create_email_verification_token(email: str, hashed_password: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFICATION_EXPIRE_HOURS)
    payload = {
        "email": email,
        "hashed_password": hashed_password,
        "purpose": EMAIL_VERIFICATION_PURPOSE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def verify_email_verification_token(token: str) -> tuple[str, str] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != EMAIL_VERIFICATION_PURPOSE:
            return None
        return payload["email"], payload["hashed_password"]
    except (jwt.PyJWTError, KeyError):
        return None