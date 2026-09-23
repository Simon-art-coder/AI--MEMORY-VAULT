"""
Application entrypoint.

For now this just proves the scaffold works: config loads, logging is
configured, and the app starts with a single health check endpoint.
Routers for auth, memories, search, etc. get included here in later phases.
"""

from fastapi import FastAPI

from app.api import auth, chat, integrations, memories, reminders, search, timeline
from app.web import routes as web_routes
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging

# Importing models here ensures SQLAlchemy's Base metadata knows about
# every table before we call create_all() below.
from app.models.user import User  # noqa: F401
from app.models.memory import Source, Memory, Person  # noqa: F401

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(auth.router, prefix="/api")
app.include_router(memories.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(reminders.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(web_routes.router)

# create_all() is a convenience for this early phase only — it creates
# tables that don't exist yet but never alters existing ones. Once the
# schema needs real changes (adding a column, etc.), we switch to Alembic
# migrations, which is the proper tool for evolving a live schema safely.
Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic liveness check — confirms the app is running and config loaded."""
    return {"status": "ok", "environment": settings.environment}
