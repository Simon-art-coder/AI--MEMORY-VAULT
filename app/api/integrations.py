"""
Source connectors (Gmail, Google Drive, calendar, messaging exports).

NOT IMPLEMENTED. This module exists so the API surface described in the
spec is present and the interface is clear, but every endpoint returns
501 Not Implemented rather than pretending to connect to anything.

What a real implementation needs before it can be built (deliberately
not started here, since faking it would violate "no fake implementation"):
- Registered OAuth apps with Google (and any other provider), with
  approved redirect URIs
- A token storage table with encryption at rest for refresh/access tokens
- A background worker to poll or subscribe to provider webhooks
- Provider-specific rate limit handling

Local file upload (app/api/memories.py) is the only working ingestion
path right now.
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/integrations", tags=["integrations"])

NOT_IMPLEMENTED_DETAIL = (
    "This connector is not implemented yet. Only local file upload "
    "(/memories/upload) works currently. See app/api/integrations.py "
    "for what's required to build this."
)


@router.get("")
def list_integrations() -> list[dict]:
    return [
        {"name": "gmail", "status": "not_implemented"},
        {"name": "google_drive", "status": "not_implemented"},
        {"name": "calendar", "status": "not_implemented"},
    ]


@router.post("/{provider}/connect")
def connect_integration(provider: str) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_IMPLEMENTED_DETAIL)


@router.delete("/{provider}")
def disconnect_integration(provider: str) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_IMPLEMENTED_DETAIL)
