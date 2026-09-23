"""
Events & decisions.

Like reminders, this only reads what extraction already produced
(extracted_facts on each Memory) — it never guesses or infers an event
from raw text itself. If extraction hasn't run on a source, nothing
from it appears here, which is correct: an un-extracted note has no
structured facts to show, not zero events.
"""

from sqlalchemy.orm import Session

from app.repositories.memory_repository import get_all_memories_for_user


def get_events_and_decisions(db: Session, user_id: str) -> list[dict]:
    memories = get_all_memories_for_user(db, user_id)
    items: list[dict] = []

    for memory in memories:
        facts = memory.extracted_facts or {}
        filename = memory.source.filename

        for event in facts.get("events", []):
            items.append(
                {
                    "kind": "event",
                    "description": event.get("description", ""),
                    "date": event.get("date"),
                    "made_by": None,
                    "source_filename": filename,
                    "recorded_at": memory.created_at,
                }
            )

        for decision in facts.get("decisions", []):
            made_by = decision.get("made_by")
            items.append(
                {
                    "kind": "decision",
                    "description": decision.get("decision", ""),
                    "date": None,
                    "made_by": ", ".join(made_by) if made_by else None,
                    "source_filename": filename,
                    "recorded_at": memory.created_at,
                }
            )

    items.sort(key=lambda i: i["recorded_at"], reverse=True)
    return items