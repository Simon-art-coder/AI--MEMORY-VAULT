"""
Password reset email sending, via Gmail SMTP.

Degrades honestly, same pattern as the AI providers: if no SMTP
credentials are configured, this raises EmailNotConfiguredError rather
than silently failing or pretending to have sent something. The route
that calls this must catch that and tell the user plainly, without
revealing whether their specific email exists in the system (to avoid
leaking which addresses are registered).
"""

import smtplib
from email.mime.text import MIMEText

from app.core.config import get_settings


class EmailNotConfiguredError(Exception):
    pass


class EmailSendError(Exception):
    pass


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    settings = get_settings()

    if not settings.smtp_username or not settings.smtp_password:
        raise EmailNotConfiguredError(
            "No SMTP credentials configured (SMTP_USERNAME / SMTP_PASSWORD in .env)."
        )

    from_email = settings.smtp_from_email or settings.smtp_username

    body = (
        "You asked to reset your AI Memory Vault password.\n\n"
        f"Click this link to choose a new password (valid for 30 minutes):\n{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email — "
        "your password will not be changed."
    )
    message = MIMEText(body)
    message["Subject"] = "Reset your AI Memory Vault password"
    message["From"] = from_email
    message["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(from_email, [to_email], message.as_string())
    except smtplib.SMTPException as exc:
        raise EmailSendError(f"Failed to send reset email: {exc}") from exc