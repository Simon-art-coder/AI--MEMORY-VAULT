"""
Retrieval-Augmented Generation pipeline.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.llm_client import LLMNotConfiguredError, LLMRequestError, generate
from app.core.config import get_settings
from app.models.memory import Memory
from app.search.search_service import search_memories

ANSWER_SYSTEM_PROMPT = """You are the user's personal memory assistant. You have access to \
excerpts retrieved from things they've written down or told you before, each labeled with the \
real date it was recorded. Answer the way a person with a good memory would — direct, natural, \
and confident when the evidence clearly supports it.

Plain text only: never use markdown formatting (no **bold**, no *italics*, no bullet points, \
no headers). Write in plain conversational sentences, since the interface displays raw text \
exactly as you write it.

Match your answer's shape to the question's shape:
- Yes/no questions ("do I have X", "did I do Y", "is Z true") → start with a clear "Yes" or "No".
- "When" questions → lead with the date/time itself, not "Yes". E.g. "You have a presentation \
  today, September 23." not "Yes, you have a presentation today."
- "What/who/where/why/how" questions → answer the specific thing asked directly, no yes/no framing.
- Never force a "Yes"/"No" preamble onto a question that isn't actually yes/no-shaped.

Date reasoning — this matters: excerpts often use RELATIVE date words ("tomorrow", "next week", \
"yesterday") written at the time they were recorded. You are told today's actual date below. \
Always resolve relative date words in an excerpt against THAT EXCERPT'S recorded date, not \
today's date, then re-express the result relative to today. For example: if an excerpt recorded \
on September 22 says "presentation tomorrow", that means September 23. If today is September 23, \
say "today"; if today is September 24, say "yesterday, September 23" and note it may have \
already happened.

Rules:
- If an excerpt directly answers the question, answer plainly and directly using the format \
  guidance above, with dates expressed relative to today, never left as the original relative \
  word from an old note.
- If the excerpts are related but don't fully answer the question, say what you do know, then \
  clearly flag what's uncertain or missing.
- If nothing relevant is in the excerpts, say plainly that you don't have that recorded. Then, \
  if it's naturally helpful, you may add ONE brief suggestion — clearly marked as a suggestion, \
  not a recalled fact.
- Never invent names, dates, or events not present in the excerpts."""


@dataclass
class RAGSource:
    memory_id: str
    source_filename: str
    excerpt: str
    relevance_score: float


@dataclass
class RAGAnswer:
    answer: str
    sources: list[RAGSource]
    answer_generated: bool


def answer_question(db: Session, user_id: str, question: str) -> RAGAnswer:
    settings = get_settings()
    results = search_memories(db, user_id, question, limit=settings.max_search_results)

    sources = [
        RAGSource(
            memory_id=memory.id,
            source_filename=memory.source.filename,
            excerpt=memory.content[:300],
            relevance_score=round(score, 4),
        )
        for memory, score in results
    ]

    if not sources:
        return RAGAnswer(
            answer="I don't have anything recorded that relates to this yet.",
            sources=[],
            answer_generated=False,
        )

    context = _build_context(results)
    today_str = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    user_message = f"Today's date: {today_str}\n\nQuestion: {question}\n\nExcerpts:\n{context}"

    try:
        answer_text = generate(ANSWER_SYSTEM_PROMPT, user_message)
        return RAGAnswer(answer=answer_text, sources=sources, answer_generated=True)
    except LLMNotConfiguredError:
        return RAGAnswer(
            answer=(
                "AI answer generation isn't configured (no GROQ_API_KEY set). "
                "Here are the raw retrieved excerpts most relevant to your question — "
                "review them yourself below."
            ),
            sources=sources,
            answer_generated=False,
        )
    except LLMRequestError as exc:
        return RAGAnswer(
            answer=f"Retrieved relevant excerpts, but answer generation failed: {exc}",
            sources=sources,
            answer_generated=False,
        )


def _build_context(results: list[tuple[Memory, float]]) -> str:
    parts = []
    for i, (memory, _score) in enumerate(results, start=1):
        recorded_date = memory.created_at.strftime("%A, %B %d, %Y")
        parts.append(
            f"[Excerpt {i} — source: {memory.source.filename} — recorded on {recorded_date}]\n"
            f"{memory.content}"
        )
    return "\n\n".join(parts)