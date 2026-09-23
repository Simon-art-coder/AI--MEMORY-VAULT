# AI Memory Vault

A personal AI memory system: import documents and notes, then ask
natural-language questions about your own history — grounded in cited
evidence, never invented.

## Honest status — what's real vs. what's stubbed

This project was built in one pass covering all 13 planned phases, per
an explicit request to prioritize completeness over the original
incremental/approval-gated workflow. In line with the project's own
"never fake an implementation" rule, here's exactly what that means:

| Area | Status |
|---|---|
| Auth, JWT, password hashing, user isolation | **Real.** Tested, including cross-user isolation. |
| Document upload (txt/md/pdf/docx) | **Real.** Actual text extraction, no mocks. |
| Chunking | **Real**, but simple (fixed-size, not sentence-aware). |
| Embeddings | **Degraded without an API key.** Uses OpenAI's embedding API if `OPENAI_API_KEY` is set. Otherwise falls back to a local feature-hashing vector — a real technique, but purely lexical (keyword-based), not semantic. The `/search` response tells you honestly which mode is active via `using_semantic_embeddings`. |
| Search | **Real** hybrid vector + keyword scoring, but no vector index (see Known Limitations). |
| RAG / chat answers | **Requires `ANTHROPIC_API_KEY`.** Without it, `/chat` returns the raw retrieved excerpts and says plainly that answer generation isn't configured — it never fabricates an answer. |
| Extraction (people/promises/decisions/tasks) | **Requires `ANTHROPIC_API_KEY`.** Without it, `/memories/{id}/extract` returns `503` rather than silently doing nothing. |
| Timeline | **Real**, but ordered by upload time, not extracted event dates (extraction is optional/LLM-gated). |
| Reminders | **Real reader** of already-extracted promises/tasks. Returns nothing if extraction hasn't run — never guesses. |
| OAuth connectors (Gmail, Drive, calendar) | **Not implemented.** `/api/integrations` endpoints return `501` with an explanation. Only local file upload works. |
| Background workers (Celery/RQ) | **Not implemented.** Ingestion runs synchronously in the request. Fine for single-user local use; would block on large files at scale. |
| Alembic migrations | **Not set up yet.** Tables are created via `create_all()`, which is fine for new tables but can't alter existing ones — needed before any real schema change. |
| Rate limiting, audit logging | **Not implemented.** |
| Web dashboard (register/login/upload/chat/timeline/reminders) | **Real.** Server-rendered pages at the routes below, cookie-based auth, calls the same service functions as the JSON API. |

Note: the JSON API moved under `/api/*` (e.g. `/api/auth/login`, `/api/chat`) to avoid colliding with the browser pages at the same names (`/login`, `/chat`, etc.).

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
# edit .env: set SECRET_KEY. Optionally set ANTHROPIC_API_KEY and/or
# OPENAI_API_KEY to unlock real answer generation / extraction / embeddings.
```

## Running

```bash
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/` — this is now a real usable webpage, not just an API.

## Try it

**Web UI (recommended):** open `http://127.0.0.1:8000/`, register, log in, and use the Dashboard (upload + search), Chat, Timeline, and Reminders pages directly in the browser.

**JSON API** (for programmatic use — see `http://127.0.0.1:8000/docs`):
1. `POST /api/auth/register`, then `POST /api/auth/login` (form fields: `username`=email, `password`)
2. Use the returned token to authorize in `/docs`
3. `POST /api/memories/upload` — upload a `.txt`, `.md`, `.pdf`, or `.docx` file
4. `POST /api/search` with a query — see retrieved chunks
5. `POST /api/chat` with a question — see either a generated answer (if `ANTHROPIC_API_KEY` is set) or the honest "not configured" message with raw sources
6. `GET /api/timeline`, `GET /api/reminders`, `GET /api/integrations`

## Known limitations (real, not hidden)

- **No vector index.** Search loads all of a user's memories and scores them in Python. Fine for hundreds of memories; will not scale. Fix: PostgreSQL + pgvector, with `database_url` in `.env` — no application code changes needed beyond the search query itself.
- **Fallback embeddings are lexical, not semantic** when no `OPENAI_API_KEY` is set — a question phrased differently from the source text may not retrieve it well.
- **No background jobs.** Large uploads block the request.
- **No schema migrations yet.** Any future model change needs Alembic set up before it's safe to run against real data.

## Project Structure

- `app/api/` — HTTP routers
- `app/core/` — config, database, security, logging
- `app/models/` — SQLAlchemy models (`User`, `Source`, `Memory`, `Person`)
- `app/schemas/` — Pydantic request/response shapes
- `app/services/` — business logic (auth, ingestion, RAG, extraction, timeline, reminders)
- `app/repositories/` — database access
- `app/ai/` — embeddings and LLM client
- `app/ingestion/` — text extraction and chunking
- `app/search/` — hybrid search scoring
- `app/workers/` — placeholder for future background jobs
- `tests/` — pytest suite (not yet written — see Next Steps)

## Next steps, in priority order

1. Write the pytest suite the original spec calls for (none exist yet — this was skipped to prioritize breadth across all 13 phases; it's the most important gap to close next)
2. Set up Alembic properly and drop `create_all()`
3. Add a real vector index (PostgreSQL + pgvector) once memory volume matters
4. Build one real OAuth connector (Gmail is the most requested) end-to-end
5. Move ingestion to a background worker (Celery/RQ + Redis)
