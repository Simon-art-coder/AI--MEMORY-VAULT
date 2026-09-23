from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.memory import ReminderItem
from app.services.reminder_service import get_outstanding_reminders

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderItem])
def reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReminderItem]:
    return get_outstanding_reminders(db, current_user.id)
