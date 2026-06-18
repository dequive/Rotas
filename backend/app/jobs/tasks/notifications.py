"""ARQ task: deliver queued transactional notifications."""

import asyncio
import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select

from app.config import get_settings
from app.modules.notifications.models import NotificationOutbox

logger = logging.getLogger(__name__)


def _send_smtp_email(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    sender: str,
    recipient: str,
    subject: str,
    body_text: str,
    body_html: str | None,
) -> None:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(host, port, timeout=20) as client:
        if use_tls:
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)


async def deliver_queued_notifications(ctx: dict, limit: int = 25) -> dict:
    settings = get_settings()
    provider = settings.email_provider.lower()
    if provider == "none":
        return {"provider": provider, "sent": 0, "failed": 0, "skipped": 0}
    if provider == "outbox":
        return {"provider": provider, "sent": 0, "failed": 0, "skipped": 0}

    session_factory = ctx["session_factory"]
    now = datetime.now(UTC)
    sent = 0
    failed = 0
    skipped = 0

    async with session_factory() as db:
        items = (
            await db.scalars(
                select(NotificationOutbox)
                .where(
                    NotificationOutbox.channel == "email",
                    NotificationOutbox.status.in_(("queued", "failed")),
                    NotificationOutbox.attempts < 5,
                    (NotificationOutbox.scheduled_at.is_(None))
                    | (NotificationOutbox.scheduled_at <= now),
                )
                .order_by(NotificationOutbox.created_at.asc())
                .limit(limit)
            )
        ).all()

        for item in items:
            item.attempts += 1
            if provider != "smtp":
                item.status = "failed"
                item.last_error = f"Unsupported EMAIL_PROVIDER: {settings.email_provider}"
                failed += 1
                continue
            try:
                await asyncio.to_thread(
                    _send_smtp_email,
                    host=settings.smtp_host,
                    port=settings.smtp_port,
                    username=settings.smtp_username,
                    password=settings.smtp_password.get_secret_value(),
                    use_tls=settings.smtp_use_tls,
                    sender=settings.email_from_address,
                    recipient=item.recipient,
                    subject=item.subject,
                    body_text=item.body_text,
                    body_html=item.body_html,
                )
                item.status = "sent"
                item.sent_at = datetime.now(UTC)
                item.last_error = None
                sent += 1
            except Exception as exc:
                item.status = "failed"
                item.last_error = str(exc)[:1000]
                failed += 1
                logger.warning("notification delivery failed id=%s: %s", item.id, exc)

        await db.commit()

    result = {"provider": provider, "sent": sent, "failed": failed, "skipped": skipped}
    logger.info("deliver_queued_notifications complete: %s", result)
    return result
