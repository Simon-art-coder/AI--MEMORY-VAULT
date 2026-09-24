"""
Structured extraction: people, events, promises, decisions, tasks.

Also auto-links extracted people to the memory via the Person table and
the memory_people association -- this turns "a name mentioned in text"
into an actual queryable relationship ("show me everything involving
John"), which the People page reads from.
"""

import json

from app.ai.llm_client import LLMNotConfiguredError, LLMRequestError, generate
from app.models.memory import Memory
from app.repositories.memory_repository import update_memory_facts
from app.repositories.person_repository import get_or_create_person, link_person_to_memory

EXTRACTION_SYSTEM_PROMPT = """You extract structured facts from a personal memory chunk of text.

Return ONLY valid JSON (no markdown, no commentary) with this exact shape:
{
  "people": ["name", ...],
  "promises": [{"who": "...", "what": "...", "deadline": "..." or null}],
  "decisions": [{"decision": "...", "made_by": [...] or null}],
  "tasks": [{"task": "...", "owner": "..." or null, "deadline": "..." or null}],
  "events": [{"description": "...", "date": "..." or null}],
  "dates_mentioned": ["..."]
}

Only include facts that are explicitly and clearly stated in the text.
Do not infer or guess. If a category has nothing, return an empty list."""


class ExtractionSkippedNotConfigured(Exception):
    pass


def extract_facts_from_text(content: str) -> dict:
    try:
        raw_response = generate(EXTRACTION_SYSTEM_PROMPT, content, max_tokens=1500)
    except LLMNotConfiguredError as exc:
        raise ExtractionSkippedNotConfigured(str(exc)) from exc

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise LLMRequestError(f"Extraction response was not valid JSON: {raw_response[:200]}") from exc


def run_extraction_for_memory(db, memory: Memory) -> Memory:
    facts = extract_facts_from_text(memory.content)
    memory = update_memory_facts(db, memory, facts)

    # Auto-link every extracted person to this memory, creating the
    # Person row if it's the first time this name has come up for this
    # user. This is what makes "who have I talked to about X" and the
    # People page possible -- without it, names sat in extracted_facts
    # as plain text with no queryable relationship at all.
    for name in facts.get("people", []):
        if not name or not name.strip():
            continue
        person = get_or_create_person(db, user_id=memory.user_id, name=name)
        link_person_to_memory(db, person, memory)

    return memory