from __future__ import annotations

from email.message import EmailMessage
from typing import Protocol

import aiosmtplib
import structlog

from kontura.core.config import settings

logger = structlog.get_logger(__name__)


class EmailSender(Protocol):
    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None: ...


class ConsoleEmailSender:
    """Loggt E-Mails strukturiert fuer lokale Entwicklung und Tests."""

    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        logger.info(
            "email_sent_console",
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )


class SmtpEmailSender:
    """Sendet E-Mails via SMTP (aiosmtplib)."""

    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        message = EmailMessage()
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_address}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)
        if body_html is not None:
            message.add_alternative(body_html, subtype="html")

        password = (
            settings.smtp_password.get_secret_value()
            if settings.smtp_password is not None
            else None
        )
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=password,
            start_tls=True,
        )
