"""
Password hashing and JWT helpers.

Keeping this in one small module means there's exactly one place in the
entire codebase that knows how passwords are hashed and how tokens are
signed. If we ever need to change either (e.g. rotate to a new hashing
cost factor), this is the only file that changes.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password with bcrypt.

    bcrypt includes a random salt automatically and encodes it into the
    output, so we never need to store a salt separately.
    """
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    """
    Create a signed JWT identifying a user.

    The token carries only the user's id ("sub") and an expiry — no
    email, no roles, nothing sensitive. Anything else the app needs
    about the user gets looked up from the database on each request,
    so a leaked token reveals as little as possible about the account.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """
    Verify a JWT and return the user id it identifies, or None if the
    token is invalid or expired. Callers treat None as "not authenticated"
    rather than distinguishing why — that's an intentional simplification;
    if we later want different handling for expired vs. tampered tokens,
    this is where that logic would go.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
