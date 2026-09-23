"""
Shared dependencies for API routes.

get_current_user is the single chokepoint every protected endpoint will
depend on. As soon as we add memories, documents, etc. in later phases,
their routes and repository queries will filter by current_user.id —
that's what turns "a database with users in it" into "user isolation."
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories import user_repository

# tokenUrl points at the login endpoint, used only so tools like the
# FastAPI docs UI know where to send credentials — it doesn't affect
# how tokens are verified here.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = user_repository.get_user_by_id(db, user_id)
    if user is None:
        raise credentials_error

    return user
