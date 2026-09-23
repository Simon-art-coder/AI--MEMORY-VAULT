"""
Structured extraction: people, events, promises, decisions, tasks.

This is the one phase that is genuinely impossible to do honestly
without an LLM — regex/keyword heuristics for "did someone make a
promise" produce too many false positives/negatives to be trustworthy,
and the spec explicitly forbids fabricating memories. So: if no
ANTHROPIC_API_KEY is set, extraction is skipped and memory.extracted_facts
stays None. This is surfaced to the caller (see run_extraction's return
value) so the API layer can tell the user honestly, instead of silently
returning empty results that look like "nothing was found."
"""

import json

from sqlalchemy.orm import Session

from app.ai.llm_client import LLMNotConfiguredError, LLMRequestError, generate
from app.models.memory import Memory
from app.repositories.memory_repository import update_memory_facts

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
    """Raised (not swallowed) when extraction can't run because no LLM key is set."""

    pass


def extract_facts_from_text(content: str) -> dict:
    try:
        raw_response = generate(EXTRACTION_SYSTEM_PROMPT, content, max_tokens=800)
    except LLMNotConfiguredError as exc:
        raise ExtractionSkippedNotConfigured(str(exc)) from exc

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        # The LLM didn't follow the JSON-only instruction. We surface this
        # as a request error rather than guessing at a partial parse —
        # a corrupted extraction is worse than a missing one.
        raise LLMRequestError(f"Extraction response was not valid JSON: {raw_response[:200]}") from exc


def run_extraction_for_memory(db: Session, memory: Memory) -> Memory:
    """
    Extracts facts for one memory chunk and persists them.
    Raises ExtractionSkippedNotConfigured if no LLM key is set — callers
    decide how to surface that (e.g. a 200 response noting extraction
    was skipped, not a fabricated empty result).
    """
    facts = extract_facts_from_text(memory.content)
    return update_memory_facts(db, memory, facts)
