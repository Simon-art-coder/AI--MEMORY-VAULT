"""
Auth for browser-rendered pages.

The JSON API (app/api/) authenticates via an Authorization: Bearer header
— the right approach for programmatic clients. Browser pages instead
carry the token in an httponly cookie, set on login, since a webpage
navigating between GET requests can't attach a header itself the way an
API client can.

Both paths decode the exact same JWT with the exact same secret — this
file doesn't reimplement auth, it just reads the token from a different
place.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories import user_repository

COOKIE_NAME = "access_token"


def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Returns the logged-in user, or None if not authenticated — pages
    decide for themselves whether to redirect to /login."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    user_id = decode_access_token(token)
    if user_id is None:
        return None

    return user_repository.get_user_by_id(db, user_id)
