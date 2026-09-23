from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.ingestion.extractors import ExtractionFailedError, UnsupportedFileTypeError
from app.models.user import User
from app.repositories import memory_repository
from app.schemas.memory import MemoryRead, SourceRead
from app.services.extraction_service import ExtractionSkippedNotConfigured, run_extraction_for_memory
from app.services.ingestion_service import ingest_document

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("/upload", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SourceRead:
    settings = get_settings()
    file_bytes = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb}MB limit",
        )

    try:
        source = ingest_document(db, user_id=current_user.id, filename=file.filename, file_bytes=file_bytes)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ExtractionFailedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return source


@router.get("", response_model=list[MemoryRead])
def list_memories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MemoryRead]:
    return memory_repository.get_all_memories_for_user(db, current_user.id)


@router.get("/{memory_id}", response_model=MemoryRead)
def get_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRead:
    memory = memory_repository.get_memory_by_id(db, current_user.id, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return memory


@router.post("/{memory_id}/extract", response_model=MemoryRead)
def extract_memory_facts(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryRead:
    """
    Runs structured extraction (Phase 8) on one memory chunk. Separate
    from upload so ingestion stays fast and extraction is opt-in — and
    so its "not configured" case is a clear, distinct response rather
    than a silent no-op during upload.
    """
    memory = memory_repository.get_memory_by_id(db, current_user.id, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    try:
        return run_extraction_for_memory(db, memory)
    except ExtractionSkippedNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.delete("/source/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    source = memory_repository.get_source_by_id(db, current_user.id, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    memory_repository.delete_source(db, source)
