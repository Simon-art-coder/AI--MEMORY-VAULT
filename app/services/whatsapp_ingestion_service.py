"""
WhatsApp export ingestion. Same chunk -> embed -> store pipeline as
document upload, using the WhatsApp-aware parser/chunker instead of the
generic sentence-boundary one, since exports are structured conversation
data (sender + timestamp per line), not prose.
"""

from sqlalchemy.orm import Session

from app.ai.embeddings import embed_text
from app.ingestion.whatsapp_parser import messages_to_chunks, parse_export
from app.models.memory import Source
from app.repositories import memory_repository


def ingest_whatsapp_export(db: Session, user_id: str, filename: str, file_bytes: bytes) -> Source:
    raw_text = file_bytes.decode("utf-8", errors="replace")
    messages = parse_export(raw_text)

    display_name = filename if filename.lower().endswith(".txt") else f"{filename} (WhatsApp export)"
    source = memory_repository.create_source(
        db,
        user_id=user_id,
        filename=display_name,
        source_type="whatsapp_export",
        raw_text_length=len(raw_text),
    )

    chunks = messages_to_chunks(messages)
    for index, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        memory_repository.create_memory(
            db, user_id=user_id, source_id=source.id, content=chunk, chunk_index=index, embedding=embedding
        )

    return source