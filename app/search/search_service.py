"""
Hybrid semantic + keyword search.
"""

import math
import re

from sqlalchemy.orm import Session

from app.ai.embeddings import embed_text
from app.models.memory import Memory
from app.repositories.memory_repository import get_all_memories_for_user

MIN_RELEVANCE_SCORE = 0.42

_STOPWORDS_EN = {
    "a", "an", "the", "i", "you", "he", "she", "it", "we", "they",
    "is", "are", "was", "were", "be", "been", "am", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should",
    "when", "where", "what", "who", "why", "how", "which",
    "in", "on", "at", "to", "for", "of", "with", "about", "my", "me",
    "this", "that", "these", "those", "and", "or", "but", "not",
}

# Swahili stopwords -- added because chat imports (WhatsApp) may be in
# Kiswahili, and without this the same common-word inflation problem
# happens in that language too. Not exhaustive, but covers the highest-
# frequency function words that would otherwise pollute every query.
_STOPWORDS_SW = {
    "na", "ya", "wa", "la", "kwa", "cha", "vya", "za",
    "hii", "hiyo", "huu", "huo", "hicho", "kile", "yule", "hili",
    "ni", "si", "kuwa", "kuna", "kama", "lakini", "au", "pia",
    "mimi", "wewe", "yeye", "sisi", "nyinyi", "wao",
    "tu", "sana", "bado", "tena", "sasa", "leo", "kesho", "jana",
    "nini", "nani", "wapi", "lini", "vipi", "gani",
}

STOPWORDS = _STOPWORDS_EN | _STOPWORDS_SW


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS}


def _keyword_overlap_score(query: str, content: str) -> float:
    query_words = _content_words(query)
    content_words = _content_words(content)
    if not query_words:
        return 0.0
    return len(query_words & content_words) / len(query_words)


def search_memories(db: Session, user_id: str, query: str, limit: int) -> list[tuple[Memory, float]]:
    query_embedding = embed_text(query)
    candidates = get_all_memories_for_user(db, user_id)

    scored: list[tuple[Memory, float]] = []
    for memory in candidates:
        vector_score = _cosine_similarity(query_embedding, memory.embedding or [])
        keyword_score = _keyword_overlap_score(query, memory.content)
        combined = (0.7 * vector_score) + (0.3 * keyword_score)
        if combined >= MIN_RELEVANCE_SCORE:
            scored.append((memory, combined))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]