"""
Browser-rendered pages.

These routes call the exact same service functions as the JSON API
(app/services/...) — there is no separate "web version" of the business
logic. Only the transport differs: HTML forms and redirects instead of
JSON request/response bodies.
"""

import logging
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.embeddings import embed_text
from app.ai.llm_client import LLMNotConfiguredError, LLMRequestError, generate
from app.core.config import get_settings
from app.core.database import get_db
from app.core.email import (
    EmailNotConfiguredError,
    EmailSendError,
    send_password_reset_email,
    send_verification_email,
)
from app.core.rate_limit import RateLimitExceededError, check_rate_limit, get_client_key, record_attempt
from app.core.security import verify_password
from app.ingestion.extractors import ExtractionFailedError, UnsupportedFileTypeError
from app.ingestion.whatsapp_parser import WhatsAppParseError
from app.models.memory import Person
from app.models.user import User
from app.repositories import user_repository
from app.repositories.memory_repository import (
    delete_source as delete_source_record,
    get_all_memories_for_user,
    get_source_by_id,
)
from app.repositories.person_repository import get_memories_for_person, get_people_for_user
from app.search.search_service import search_memories
from app.services import auth_service
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidOrExpiredResetTokenError,
    InvalidOrExpiredVerificationTokenError,
)
from app.services.capture_service import capture_note
from app.services.events_service import get_events_and_decisions
from app.services.extraction_service import ExtractionSkippedNotConfigured, run_extraction_for_memory
from app.services.ingestion_service import ingest_document
from app.services.rag_service import answer_question
from app.services.reminder_service import get_outstanding_reminders
from app.services.timeline_service import get_timeline
from app.services.whatsapp_ingestion_service import ingest_whatsapp_export
from app.web.auth_web import COOKIE_NAME, get_current_user_from_cookie

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
# Workaround for a known Jinja2/Python 3.14 incompatibility: the template
# cache's key construction breaks under 3.14 ("cannot use 'tuple' as a
# dict key"). Disabling the cache avoids it — templates are small here,
# so re-parsing on each request has negligible cost.
templates.env.cache = None

logger = logging.getLogger(__name__)


def _ai_configured() -> bool:
    return bool(get_settings().groq_api_key)


def _embedding_provider(settings) -> str:
    if settings.gemini_api_key:
        return "Gemini (gemini-embedding-001)"
    if settings.openai_api_key:
        return "OpenAI (text-embedding-3-small)"
    return "local fallback (no key set)"


def _check_db(db: Session) -> tuple[bool, str | None]:
    try:
        db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def _build_memory_groups(memories) -> list[dict]:
    """Groups a flat list of Memory chunks by their source document/note."""
    groups: dict[str, dict] = {}
    for m in memories:
        key = m.source_id
        if key not in groups:
            groups[key] = {
                "source_id": key,
                "filename": m.source.filename,
                "created_at": m.source.created_at,
                "chunks": [],
                "has_facts": False,
            }
        groups[key]["chunks"].append(m.content)
        if m.extracted_facts:
            groups[key]["has_facts"] = True
    return list(groups.values())


@router.get("/", response_class=HTMLResponse)
def root(user: User | None = Depends(get_current_user_from_cookie)):
    return RedirectResponse("/dashboard" if user else "/login")


# --- Auth pages ---

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"user": None, "error": None, "message": None})


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    rate_key = get_client_key(request, "register")
    try:
        check_rate_limit(rate_key, max_attempts=3, window_seconds=600)
    except RateLimitExceededError as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"user": None, "error": f"Too many attempts. Try again in {exc.retry_after_seconds} seconds.", "message": None},
        )
    record_attempt(rate_key)

    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"user": None, "error": "Passwords do not match.", "message": None},
        )

    try:
        validated = validate_email(email, check_deliverability=True)
        email = validated.normalized
    except EmailNotValidError as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"user": None, "error": f"Please enter a valid email address: {exc}", "message": None},
        )

    try:
        token = auth_service.create_verification_token_for_new_user(db, email=email, password=password)
    except EmailAlreadyRegisteredError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"user": None, "error": "An account with this email already exists.", "message": None},
        )

    verify_link = f"{str(request.base_url).rstrip('/')}/verify-email?token={token}"

    try:
        send_verification_email(email, verify_link)
    except EmailNotConfiguredError:
        auth_service.register_user(db, email=email, password=password)
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "user": None,
                "error": None,
                "message": (
                    "Email verification isn't configured on this server, so your account "
                    "was created immediately. You can log in now."
                ),
            },
        )
    except EmailSendError as exc:
        auth_service.register_user(db, email=email, password=password)
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "user": None,
                "error": None,
                "message": (
                    f"Your account was created, but the confirmation email failed to send "
                    f"({exc}). You can log in now — this is worth fixing on the server."
                ),
            },
        )

    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "user": None,
            "error": None,
            "message": f"Check {email} for a confirmation link to finish creating your account.",
        },
    )


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    try:
        auth_service.complete_registration(db, token=token)
    except (InvalidOrExpiredVerificationTokenError, EmailAlreadyRegisteredError) as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"user": None, "error": str(exc), "message": None},
        )

    return templates.TemplateResponse(
        request,
        "register.html",
        {"user": None, "error": None, "message": "Your account is confirmed. You can log in now."},
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)
):
    rate_key = get_client_key(request, "login")
    try:
        check_rate_limit(rate_key, max_attempts=5, window_seconds=300)
    except RateLimitExceededError as exc:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": f"Too many attempts. Try again in {exc.retry_after_seconds} seconds."},
        )
    record_attempt(rate_key)

    try:
        token = auth_service.authenticate_user(db, email=email, password=password)
    except InvalidCredentialsError:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": "Incorrect email or password."},
        )

    response = RedirectResponse("/dashboard", status_code=303)
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME, token, httponly=True,
        secure=(settings.environment == "production"),
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# --- Password reset ---

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request, "forgot_password.html", {"user": None, "message": None, "error": None}
    )


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    rate_key = get_client_key(request, "forgot-password")
    try:
        check_rate_limit(rate_key, max_attempts=3, window_seconds=600)
    except RateLimitExceededError as exc:
        return templates.TemplateResponse(
            request,
            "forgot_password.html",
            {"user": None, "message": None, "error": f"Too many attempts. Try again in {exc.retry_after_seconds} seconds."},
        )
    record_attempt(rate_key)

    try:
        validated = validate_email(email, check_deliverability=True)
        email = validated.normalized
    except EmailNotValidError:
        return templates.TemplateResponse(
            request,
            "forgot_password.html",
            {"user": None, "message": None, "error": "Please enter a valid email address."},
        )

    generic_message = "If that email is registered, a password reset link has been sent."

    token = auth_service.create_reset_token_for_email(db, email)
    if token is not None:
        reset_link = f"{str(request.base_url).rstrip('/')}/reset-password?token={token}"
        try:
            send_password_reset_email(email, reset_link)
        except (EmailNotConfiguredError, EmailSendError):
            pass

    return templates.TemplateResponse(
        request, "forgot_password.html", {"user": None, "message": generic_message, "error": None}
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(
        request, "reset_password.html", {"user": None, "token": token, "error": None}
    )


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"user": None, "token": token, "error": "Passwords do not match."},
        )

    try:
        auth_service.reset_password_with_token(db, token=token, new_password=new_password)
    except InvalidOrExpiredResetTokenError as exc:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"user": None, "token": token, "error": str(exc)},
        )

    return RedirectResponse("/login", status_code=303)


# --- App pages (require login) ---

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    q: str | None = None,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    memory_groups = _build_memory_groups(get_all_memories_for_user(db, user.id))

    search_results = None
    if q:
        settings = get_settings()
        results = search_memories(db, user.id, q, limit=settings.max_search_results)
        search_results = [
            {"source_filename": m.source.filename, "excerpt": m.content[:200], "relevance_score": score}
            for m, score in results
        ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "memory_groups": memory_groups,
            "query": q,
            "search_results": search_results,
            "ai_configured": _ai_configured(),
            "upload_error": None,
            "whatsapp_error": None,
        },
    )


@router.post("/dashboard/upload", response_class=HTMLResponse)
async def dashboard_upload(
    request: Request,
    file: UploadFile,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    file_bytes = await file.read()
    try:
        ingest_document(db, user_id=user.id, filename=file.filename, file_bytes=file_bytes)
    except (UnsupportedFileTypeError, ExtractionFailedError) as exc:
        memory_groups = _build_memory_groups(get_all_memories_for_user(db, user.id))
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "memory_groups": memory_groups,
                "query": None,
                "search_results": None,
                "upload_error": str(exc),
                "whatsapp_error": None,
                "ai_configured": _ai_configured(),
            },
        )

    return RedirectResponse("/dashboard", status_code=303)


@router.post("/dashboard/upload-whatsapp", response_class=HTMLResponse)
async def dashboard_upload_whatsapp(
    request: Request,
    file: UploadFile,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    file_bytes = await file.read()
    try:
        ingest_whatsapp_export(db, user_id=user.id, filename=file.filename, file_bytes=file_bytes)
    except WhatsAppParseError as exc:
        memory_groups = _build_memory_groups(get_all_memories_for_user(db, user.id))
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "memory_groups": memory_groups,
                "query": None,
                "search_results": None,
                "upload_error": None,
                "whatsapp_error": str(exc),
                "ai_configured": _ai_configured(),
            },
        )

    return RedirectResponse("/dashboard", status_code=303)


@router.post("/dashboard/delete-source/{source_id}")
def dashboard_delete_source(
    source_id: str,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    source = get_source_by_id(db, user.id, source_id)
    if source is not None:
        delete_source_record(db, source)

    return RedirectResponse("/dashboard", status_code=303)


@router.post("/dashboard/extract-source/{source_id}")
def dashboard_extract_source(
    request: Request,
    source_id: str,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    memories = [m for m in get_all_memories_for_user(db, user.id) if m.source_id == source_id]
    not_configured = False
    error_message = None

    for memory in memories:
        try:
            run_extraction_for_memory(db, memory)
        except ExtractionSkippedNotConfigured:
            not_configured = True
            break
        except Exception as exc:
            logger.exception("Extraction failed for memory %s", memory.id)
            error_message = f"Extraction failed: {exc}"
            continue

    memory_groups = _build_memory_groups(get_all_memories_for_user(db, user.id))
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "memory_groups": memory_groups,
            "query": None,
            "search_results": None,
            "upload_error": None,
            "whatsapp_error": (
                "GROQ_API_KEY isn't configured, so extraction can't run." if not_configured else error_message
            ),
            "ai_configured": _ai_configured(),
        },
    )


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, user: User | None = Depends(get_current_user_from_cookie)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "chat.html", {"user": user})


@router.post("/chat", response_class=HTMLResponse)
def chat_submit(
    request: Request,
    question: str = Form(...),
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    result = answer_question(db, user.id, question)
    sources = [
        {"source_filename": s.source_filename, "excerpt": s.excerpt, "relevance_score": s.relevance_score}
        for s in result.sources
    ]

    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "user": user,
            "question": question,
            "answer": result.answer,
            "answer_generated": result.answer_generated,
            "sources": sources,
        },
    )


@router.post("/chat/capture", response_class=HTMLResponse)
def chat_capture(
    request: Request,
    note: str = Form(...),
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    capture_note(db, user_id=user.id, text=note)

    return templates.TemplateResponse(
        request,
        "chat.html",
        {"user": user, "capture_saved": True},
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "profile.html", {"user": user, "delete_error": None})


@router.post("/profile/delete-account")
def delete_account(
    request: Request,
    password: str = Form(...),
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    if not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "profile.html",
            {"user": user, "delete_error": "Incorrect password. Your account was not deleted."},
        )

    user_repository.delete_user(db, user)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/people", response_class=HTMLResponse)
def people_page(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    people = get_people_for_user(db, user.id)
    return templates.TemplateResponse(request, "people.html", {"user": user, "people": people})


@router.get("/people/{person_id}", response_class=HTMLResponse)
def person_detail_page(
    request: Request,
    person_id: str,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    person = db.scalars(select(Person).where(Person.user_id == user.id, Person.id == person_id)).first()
    if person is None:
        return RedirectResponse("/people", status_code=303)

    memories = get_memories_for_person(db, user.id, person_id)
    return templates.TemplateResponse(
        request, "person_detail.html", {"user": user, "person": person, "memories": memories}
    )


@router.get("/events", response_class=HTMLResponse)
def events_page(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    events = get_events_and_decisions(db, user.id)
    return templates.TemplateResponse(
        request,
        "events.html",
        {"user": user, "events": events, "ai_configured": _ai_configured()},
    )


@router.get("/timeline", response_class=HTMLResponse)
def timeline_page(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    entries = get_timeline(db, user.id)
    return templates.TemplateResponse(request, "timeline.html", {"user": user, "entries": entries})


@router.get("/reminders", response_class=HTMLResponse)
def reminders_page(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    reminders = get_outstanding_reminders(db, user.id)
    return templates.TemplateResponse(
        request,
        "reminders.html",
        {"user": user, "reminders": reminders, "ai_configured": _ai_configured()},
    )


# --- Status page ---

@router.get("/status", response_class=HTMLResponse)
def status_page(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    settings = get_settings()
    db_ok, db_error = _check_db(db)

    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "user": user,
            "db_ok": db_ok,
            "db_error": db_error,
            "groq_configured": bool(settings.groq_api_key),
            "llm_model": settings.llm_model,
            "embedding_provider": _embedding_provider(settings),
            "chat_test_result": None,
            "chat_test_ok": None,
            "embed_test_result": None,
            "embed_test_ok": None,
        },
    )


@router.post("/status/test-chat", response_class=HTMLResponse)
def status_test_chat(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    settings = get_settings()
    result, ok = None, False
    try:
        generate("You are a test.", "Reply with the single word: OK", max_tokens=10)
        result, ok = "✅ Chat API responded successfully.", True
    except LLMNotConfiguredError as exc:
        result = f"⚠ {exc}"
    except LLMRequestError as exc:
        result = f"❌ {exc}"

    db_ok, db_error = _check_db(db)

    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "user": user,
            "db_ok": db_ok,
            "db_error": db_error,
            "groq_configured": bool(settings.groq_api_key),
            "llm_model": settings.llm_model,
            "embedding_provider": _embedding_provider(settings),
            "chat_test_result": result,
            "chat_test_ok": ok,
            "embed_test_result": None,
            "embed_test_ok": None,
        },
    )


@router.post("/status/test-embeddings", response_class=HTMLResponse)
def status_test_embeddings(
    request: Request,
    user: User | None = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)

    settings = get_settings()
    result, ok = None, False
    try:
        vector = embed_text("test")
        result, ok = f"✅ Embeddings API responded successfully ({len(vector)} dimensions).", True
    except Exception as exc:
        result = f"❌ {exc}"

    db_ok, db_error = _check_db(db)

    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "user": user,
            "db_ok": db_ok,
            "db_error": db_error,
            "groq_configured": bool(settings.groq_api_key),
            "llm_model": settings.llm_model,
            "embedding_provider": _embedding_provider(settings),
            "chat_test_result": None,
            "chat_test_ok": None,
            "embed_test_result": result,
            "embed_test_ok": ok,
        },
    )