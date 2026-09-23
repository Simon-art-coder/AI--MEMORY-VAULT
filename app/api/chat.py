from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.memory import ChatRequest, ChatResponse, SearchResultItem
from app.services.rag_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    result = answer_question(db, current_user.id, payload.question)

    sources = [
        SearchResultItem(
            memory_id=s.memory_id,
            source_filename=s.source_filename,
            excerpt=s.excerpt,
            relevance_score=s.relevance_score,
        )
        for s in result.sources
    ]

    return ChatResponse(answer=result.answer, answer_generated=result.answer_generated, sources=sources)
