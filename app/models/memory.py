import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

def _new_id(): return str(uuid.uuid4())

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_text_length: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    memories: Mapped[list["Memory"]] = relationship(back_populates="source", cascade="all, delete-orphan")

memory_people = Table(
    "memory_people",
    Base.metadata,
    Column("memory_id", String(36), ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", String(36), ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
)

class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(default=0)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extracted_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    source: Mapped["Source"] = relationship(back_populates="memories")
    people: Mapped[list["Person"]] = relationship(secondary=memory_people, back_populates="memories")

class Person(Base):
    __tablename__ = "people"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    memories: Mapped[list["Memory"]] = relationship(secondary=memory_people, back_populates="people")