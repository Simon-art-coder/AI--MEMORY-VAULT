"""
Transactional email sending, via Brevo's HTTPS API.

Previously used raw SMTP (Gmail), which worked locally but failed on
Render with "[Errno 101] Network is unreachable" -- confirmed via
Render's own changelog: free web services block ALL outbound traffic on
SMTP ports 25, 465, and 587 as of September 2025, specifically to fight
spam abuse. This is a permanent platform policy -- SMTP simply cannot
work from a free Render service, regardless of provider.

The fix: send email over HTTPS instead. Brevo's transactional email
REST API does the same job over port 443, which is never blocked.
Free tier: 300 emails/day, no credit card required.
"""

import httpx

from app.core.config import get_settings

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailNotConfiguredError(Exception):
    pass


class EmailSendError(Exception):
    pass


def _send(to_email: str, subject: str, text_content: str) -> None:
    settings = get_settings()

    if not settings.brevo_api_key or not settings.brevo_sender_email:
        raise EmailNotConfiguredError(
            "No Brevo credentials configured (BREVO_API_KEY / BREVO_SENDER_EMAIL in .env)."
        )

    payload = {
        "sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text_content,
    }

    try:
        response = httpx.post(
            BREVO_API_URL,
            headers={
                "accept": "application/json",
                "api-key": settings.brevo_api_key,
                "content-type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Failed to send email: {exc}") from exc


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    body = (
        "You asked to reset your AI Memory Vault password.\n\n"
        f"Click this link to choose a new password (valid for 30 minutes):\n{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email — "
        "your password will not be changed."
    )
    _send(to_email, "Reset your AI Memory Vault password", body)


def send_verification_email(to_email: str, verify_link: str) -> None:
    body = (
        "Welcome to AI Memory Vault!\n\n"
        f"Click this link to confirm your email and finish creating your account "
        f"(valid for 24 hours):\n{verify_link}\n\n"
        "If you didn't request this, you can safely ignore this email — "
        "no account will be created."
    )
    _send(to_email, "Confirm your AI Memory Vault account", body)