"""
Authentication business logic.
"""

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    hash_password,
    verify_password,
    verify_email_verification_token,
    verify_password_reset_token,
)
from app.models.user import User
from app.repositories import user_repository


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidOrExpiredResetTokenError(Exception):
    pass


class InvalidOrExpiredVerificationTokenError(Exception):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    if user_repository.get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError(f"Email already registered: {email}")
    return user_repository.create_user(db, email=email, hashed_password=hash_password(password))


def create_verification_token_for_new_user(db: Session, email: str, password: str) -> str:
    if user_repository.get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError(f"Email already registered: {email}")
    return create_email_verification_token(email, hash_password(password))


def complete_registration(db: Session, token: str) -> User:
    result = verify_email_verification_token(token)
    if result is None:
        raise InvalidOrExpiredVerificationTokenError(
            "This confirmation link is invalid or has expired."
        )

    email, hashed_password = result

    if user_repository.get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError(f"Email already registered: {email}")

    return user_repository.create_user(db, email=email, hashed_password=hashed_password)


def authenticate_user(db: Session, email: str, password: str) -> str:
    user = user_repository.get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect email or password")
    return create_access_token(user_id=user.id)


def create_reset_token_for_email(db: Session, email: str) -> str | None:
    user = user_repository.get_user_by_email(db, email)
    if user is None:
        return None
    return create_password_reset_token(user_id=user.id)


def reset_password_with_token(db: Session, token: str, new_password: str) -> None:
    user_id = verify_password_reset_token(token)
    if user_id is None:
        raise InvalidOrExpiredResetTokenError("This reset link is invalid or has expired.")

    user = user_repository.get_user_by_id(db, user_id)
    if user is None:
        raise InvalidOrExpiredResetTokenError("This reset link is invalid or has expired.")

    user.hashed_password = hash_password(new_password)
    db.commit()