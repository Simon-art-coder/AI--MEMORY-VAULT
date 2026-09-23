"""
Core memory-domain models.

We deliberately did NOT create a table for every noun in the spec
(Event, Promise, Decision, Task, Deadline as separate tables). Reason:
we don't yet know the real query patterns, and premature normalization
means painful migrations later. Instead:

- Source: one row per uploaded document/note (the file itself).
- Memory: one row per chunk of extracted text — the actual retrievable
  unit for search and RAG. Carries its embedding and, once extraction
  runs, a JSON blob of structured facts (people/promises/decisions/etc).
- Person: promoted to a real table because "who talked to whom" is a
  relationship query we know we need (Phase 8), and a loose text field
  can't support that.

If usage later shows that promises/tasks/decisions need their own
indexed columns (e.g. querying "all overdue tasks" efficiently), that's
a clean, deliberate migration — not a guess we bake in now.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


class Source(Base):
    """A single uploaded document — the file-level record."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, txt, md
    raw_text_length: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    memories: Mapped[list["Memory"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Memory(Base):
    """
    One retrievable chunk of text, with its provenance and (optionally)
    its embedding and extracted structured facts.
    """

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(default=0)

    # Stored as JSON (a plain list of floats). This is an MVP compromise —
    # see app/ai/embeddings.py for why, and app/search/vector_search.py for
    # how similarity is computed without a real vector index like pgvector.
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Structured facts pulled out by app/services/extraction_service.py:
    # {"people": [...], "promises": [...], "decisions": [...], "tasks": [...],
    #  "events": [...], "dates_mentioned": [...]}
    # Null until extraction has run (or been skipped because no LLM key is set).
    extracted_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    source: Mapped["Source"] = relationship(back_populates="memories")


class Person(Base):
    """A person mentioned across a user's memories, for relationship queries."""

    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
