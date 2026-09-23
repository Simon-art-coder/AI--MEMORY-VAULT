"""
Database engine and session setup.

We create ONE engine for the whole application (SQLAlchemy manages
pooling internally) and hand out a fresh Session per request via
get_db(), a FastAPI dependency. Routes never import the engine directly —
they depend on get_db() so the session lifecycle stays predictable:
opened at the start of a request, closed at the end, no leaks.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# check_same_thread=False is only needed for SQLite, which otherwise
# refuses to share a connection across threads. It's a no-op / ignored
# for PostgreSQL, so this line stays harmless when we switch databases.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class every SQLAlchemy model inherits from."""

    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and guarantees
    it's closed afterward, even if the request raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
