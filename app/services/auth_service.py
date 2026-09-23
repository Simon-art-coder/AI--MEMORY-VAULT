"""
Authentication business logic.

Routes call these functions and translate the results into HTTP
responses. The service layer knows nothing about HTTP — it raises plain
Python exceptions, which the API layer maps to status codes. That keeps
this logic testable without spinning up a web server.
"""

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories import user_repository


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    if user_repository.get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError(f"Email already registered: {email}")

    return user_repository.create_user(db, email=email, hashed_password=hash_password(password))


def authenticate_user(db: Session, email: str, password: str) -> str:
    """
    Verify credentials and return a signed access token.

    We deliberately give the same error for "no such user" and "wrong
    password" — telling an attacker which one it was would let them
    enumerate registered email addresses.
    """
    user = user_repository.get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect email or password")

    return create_access_token(user_id=user.id)
