"""
Transactional email sending, via Gmail SMTP.
"""

import smtplib
from email.mime.text import MIMEText

from app.core.config import get_settings


class EmailNotConfiguredError(Exception):
    pass


class EmailSendError(Exception):
    pass


def _send(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()

    if not settings.smtp_username or not settings.smtp_password:
        raise EmailNotConfiguredError(
            "No SMTP credentials configured (SMTP_USERNAME / SMTP_PASSWORD in .env)."
        )

    from_email = settings.smtp_from_email or settings.smtp_username
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(from_email, [to_email], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
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