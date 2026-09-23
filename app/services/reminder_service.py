"""
Reminders / outstanding commitments.

This reads whatever extraction already produced (extracted_facts on each
Memory) — it does NOT run its own detection. If extraction hasn't run
(no LLM key configured), this correctly returns an empty list rather
than falling back to guessing at commitments from raw text, which would
risk exactly the kind of fabricated/false "reminder" the spec explicitly
warns against.

No push notifications or scheduled alerts are implemented — this is a
read endpoint only ("what's outstanding right now"), per the original
spec's instruction not to silently create intrusive reminders.
"""

from sqlalchemy.orm import Session

from app.repositories.memory_repository import get_all_memories_for_user


def get_outstanding_reminders(db: Session, user_id: str) -> list[dict]:
    memories = get_all_memories_for_user(db, user_id)
    reminders = []

    for memory in memories:
        facts = memory.extracted_facts or {}
        filename = memory.source.filename

        for promise in facts.get("promises", []):
            reminders.append(
                {
                    "kind": "promise",
                    "description": promise.get("what", ""),
                    "deadline": promise.get("deadline"),
                    "owner": promise.get("who"),
                    "source_filename": filename,
                }
            )

        for task in facts.get("tasks", []):
            reminders.append(
                {
                    "kind": "task",
                    "description": task.get("task", ""),
                    "deadline": task.get("deadline"),
                    "owner": task.get("owner"),
                    "source_filename": filename,
                }
            )

    return reminders
