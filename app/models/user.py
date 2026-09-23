"""
User model.

Every piece of data in this app — every memory, document, and eventually
every extracted person/promise/task — belongs to exactly one User via a
user_id foreign key. This table is the anchor for that isolation.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    # UUID primary keys instead of auto-incrementing integers: they don't
    # reveal how many users exist or leak signup order, and they're safe
    # to expose in URLs/tokens without an attacker guessing neighboring ids.
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
