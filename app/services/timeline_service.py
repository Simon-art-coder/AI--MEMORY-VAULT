"""
Timeline generation.

For this phase, the timeline is ordered by each memory's created_at
(when it was ingested), not by dates mentioned inside the text — that
would require reliably parsing natural-language dates out of
extracted_facts.dates_mentioned, which is only populated when extraction
has run (i.e. an LLM key is set). Once that's reliable, this should sort
by extracted event dates instead of ingestion time. Noted as a known
simplification, not hidden.
"""

from sqlalchemy.orm import Session

from app.repositories.memory_repository import get_all_memories_for_user


def get_timeline(db: Session, user_id: str) -> list[dict]:
    memories = get_all_memories_for_user(db, user_id)
    return [
        {
            "date": memory.created_at,
            "source_filename": memory.source.filename,
            "excerpt": memory.content[:200],
        }
        for memory in memories
    ]
