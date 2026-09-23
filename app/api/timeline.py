from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.memory import TimelineEntry
from app.services.timeline_service import get_timeline

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("", response_model=list[TimelineEntry])
def timeline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TimelineEntry]:
    return get_timeline(db, current_user.id)
