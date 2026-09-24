"""
Data access for sources and memories.
"""

from sqlalchemy import select
from sqlalchemy.orm import defer

from app.models.memory import Memory, Source


def create_source(db, user_id: str, filename: str, source_type: str, raw_text_length: int) -> Source:
    source = Source(
        user_id=user_id, filename=filename, source_type=source_type, raw_text_length=raw_text_length
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def create_memory(db, user_id: str, source_id: str, content: str, chunk_index: int, embedding: list | None) -> Memory:
    memory = Memory(
        user_id=user_id, source_id=source_id, content=content, chunk_index=chunk_index, embedding=embedding
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def get_all_memories_for_user(db, user_id: str) -> list[Memory]:
    """
    Full version, including the embedding column. Only search_memories()
    (app/search/search_service.py) should use this -- it's the only
    caller that genuinely needs the embedding vector, to compute cosine
    similarity against the query.
    """
    stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at.desc())
    return list(db.scalars(stmt))


def get_all_memories_for_user_light(db, user_id: str) -> list[Memory]:
    """
    Same as get_all_memories_for_user, but never loads the embedding
    column -- a list of hundreds or thousands of floats per row that
    the dashboard, upload, and extraction listings never actually use
    (only search_memories() genuinely needs it). Loading it anyway on
    every dashboard page view scales with how much a user has stored,
    and is a real, growing contributor to hitting Render's free-tier
    512MB memory ceiling as the vault grows. Use this for anything that
    only displays or filters memories without touching their vectors.
    """
    stmt = (
        select(Memory)
        .options(defer(Memory.embedding))
        .where(Memory.user_id == user_id)
        .order_by(Memory.created_at.desc())
    )
    return list(db.scalars(stmt))


def get_source_by_id(db, user_id: str, source_id: str) -> Source | None:
    stmt = select(Source).where(Source.user_id == user_id, Source.id == source_id)
    return db.scalars(stmt).first()


def delete_source(db, source: Source) -> None:
    db.delete(source)
    db.commit()


def update_memory_facts(db, memory: Memory, facts: dict) -> Memory:
    memory.extracted_facts = facts
    db.commit()
    db.refresh(memory)
    return memory