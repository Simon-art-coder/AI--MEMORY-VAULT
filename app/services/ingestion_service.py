"""
Ingestion pipeline orchestration.

SOURCE -> VALIDATE -> EXTRACT -> CHUNK -> EMBED -> STORE

This function only coordinates; each step's real logic lives in its own
module (app.ingestion.extractors, app.ingestion.chunking, app.ai.embeddings).
Extraction of structured facts (people/promises/decisions) is a separate,
later step — see extraction_service.py — not part of this pipeline, so
ingestion stays fast even when no LLM key is configured.

Runs synchronously for this phase. A real deployment would push this
onto a background worker (Celery/RQ) so a large upload doesn't block the
request — deferred here because that requires a running Redis instance,
which isn't set up in this environment yet. The interface (this function
signature) wouldn't change when that's added; it would just be called
from a worker task instead of the request handler.
"""

from sqlalchemy.orm import Session

from app.ai.embeddings import embed_text
from app.ingestion.chunking import chunk_text
from app.ingestion.extractors import extract_text
from app.models.memory import Source
from app.repositories import memory_repository
from app.core.config import get_settings


def ingest_document(db: Session, user_id: str, filename: str, file_bytes: bytes) -> Source:
    settings = get_settings()

    raw_text = extract_text(filename, file_bytes)
    extension = filename.rsplit(".", 1)[-1].lower()

    source = memory_repository.create_source(
        db, user_id=user_id, filename=filename, source_type=extension, raw_text_length=len(raw_text)
    )

    chunks = chunk_text(raw_text, settings.chunk_size_chars, settings.chunk_overlap_chars)

    for index, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        memory_repository.create_memory(
            db,
            user_id=user_id,
            source_id=source.id,
            content=chunk,
            chunk_index=index,
            embedding=embedding,
        )

    return source
