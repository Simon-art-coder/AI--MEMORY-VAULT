from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.embeddings import is_using_real_embeddings
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.memory import SearchQuery, SearchResponse, SearchResultItem
from app.search.search_service import search_memories

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    payload: SearchQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    settings = get_settings()
    results = search_memories(db, current_user.id, payload.query, limit=settings.max_search_results)

    items = [
        SearchResultItem(
            memory_id=memory.id,
            source_filename=memory.source.filename,
            excerpt=memory.content[:300],
            relevance_score=round(score, 4),
        )
        for memory, score in results
    ]

    return SearchResponse(results=items, using_semantic_embeddings=is_using_real_embeddings())
