"""
Chat-based memory capture.

Reuses the exact same chunk -> embed -> store pipeline as file upload
(see ingestion_service.py) — the only difference is the source: typed
text instead of an uploaded file's extracted text.

Deliberately NOT automatic: this only runs when the user explicitly
submits the "tell me something" form, never on every chat message.
Asking a question (/chat) and recording a memory (/capture) stay two
separate, explicit actions.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.embeddings import embed_text
from app.core.config import get_settings
from app.ingestion.chunking import chunk_text
from app.models.memory import Source
from app.repositories import memory_repository


def capture_note(db: Session, user_id: str, text: str) -> Source:
    settings = get_settings()
    text = text.strip()

    if not text:
        raise ValueError("Cannot capture an empty note")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    filename = f"Note - {timestamp}"

    source = memory_repository.create_source(
        db, user_id=user_id, filename=filename, source_type="note", raw_text_length=len(text)
    )

    chunks = chunk_text(text, settings.chunk_size_chars, settings.chunk_overlap_chars)
    for index, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        memory_repository.create_memory(
            db, user_id=user_id, source_id=source.id, content=chunk, chunk_index=index, embedding=embedding
        )

    return source