"""
Data access for sources and memories.

Every function here takes user_id and filters by it — this is the
concrete mechanism behind "one user can never see another user's data."
There is no function in this file that returns memories without a
user_id filter; that's deliberate, not an oversight.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import Memory, Source


def create_source(db: Session, user_id: str, filename: str, source_type: str, raw_text_length: int) -> Source:
    source = Source(
        user_id=user_id, filename=filename, source_type=source_type, raw_text_length=raw_text_length
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def create_memory(
    db: Session,
    user_id: str,
    source_id: str,
    content: str,
    chunk_index: int,
    embedding: list[float] | None,
) -> Memory:
    memory = Memory(
        user_id=user_id,
        source_id=source_id,
        content=content,
        chunk_index=chunk_index,
        embedding=embedding,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def get_all_memories_for_user(db: Session, user_id: str) -> list[Memory]:
    stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at.desc())
    return list(db.scalars(stmt))


def get_memory_by_id(db: Session, user_id: str, memory_id: str) -> Memory | None:
    stmt = select(Memory).where(Memory.user_id == user_id, Memory.id == memory_id)
    return db.scalars(stmt).first()


def get_source_by_id(db: Session, user_id: str, source_id: str) -> Source | None:
    stmt = select(Source).where(Source.user_id == user_id, Source.id == source_id)
    return db.scalars(stmt).first()


def update_memory_facts(db: Session, memory: Memory, facts: dict) -> Memory:
    memory.extracted_facts = facts
    db.commit()
    db.refresh(memory)
    return memory


def delete_source(db: Session, source: Source) -> None:
    # Memory rows cascade via the relationship's cascade="all, delete-orphan"
    # and the FK's ON DELETE CASCADE — deleting the source is enough.
    db.delete(source)
    db.commit()
