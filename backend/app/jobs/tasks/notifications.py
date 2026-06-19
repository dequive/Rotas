"""ARQ task: deliver queued transactional notifications."""

import asyncio
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select

from app.config import get_settings
from app.modules.notifications.models import NotificationOutbox

logger = logging.getLogger(__name__)

# RC-03: Exponential backoff delays (seconds) indexed by attempt number (0-based).
# Attempt 0 → 1 min, 1 → 5 min, 2 → 15 min, 3 → 1 h, 4 → 2 h.
_RETRY_DELAYS = [60, 300, 900, 3600, 7200]
MAX_ATTEMPTS = 5


def _next_retry_at(attempts: int) -> datetime:
    """Return the earliest datetime at which the next delivery attempt may run."""
    delay = _RETRY_DELAYS[min(attempts, len(_RETRY_DELAYS) - 1)]
    return datetime.now(UTC) + timedelta(seconds=delay)


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
        return {"provider": provider, "sent": 0, "failed": 0, "skipped": 0, "dead_letter": 0}
    if provider == "outbox":
        return {"provider": provider, "sent": 0, "failed": 0, "skipped": 0, "dead_letter": 0}

    session_factory = ctx["session_factory"]
    now = datetime.now(UTC)
    sent = 0
    failed = 0
    skipped = 0
    dead_letter = 0

    async with session_factory() as db:
        items = (
            await db.scalars(
                select(NotificationOutbox)
                .where(
                    NotificationOutbox.channel == "email",
                    NotificationOutbox.status.in_(("queued", "failed")),
                    NotificationOutbox.attempts < MAX_ATTEMPTS,
                    (NotificationOutbox.scheduled_at.is_(None))
                    | (NotificationOutbox.scheduled_at <= now),
                )
                .order_by(NotificationOutbox.created_at.asc())
                .limit(limit)
            )
        ).all()

        for item in items:
            item.attempts += 1
            attempt_label = f"{item.attempts}/{MAX_ATTEMPTS}"

            if provider != "smtp":
                item.status = "failed"
                item.last_error = f"Unsupported EMAIL_PROVIDER: {settings.email_provider}"
                item.scheduled_at = _next_retry_at(item.attempts)
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
                item.scheduled_at = None
                sent += 1
                logger.info(
                    "notification sent id=%s attempt=%s recipient=%s",
                    item.id,
                    attempt_label,
                    item.recipient,
                )
            except Exception as exc:
                item.last_error = str(exc)[:1000]
                if item.attempts >= MAX_ATTEMPTS:
                    # RC-03: Move to dead-letter after exhausting all retries so
                    # operators can inspect and replay without the cron endlessly
                    # burning connections against an unavailable SMTP server.
                    item.status = "dead_letter"
                    item.scheduled_at = None
                    dead_letter += 1
                    logger.error(
                        "notification dead-lettered id=%s after %s attempts: %s",
                        item.id,
                        attempt_label,
                        exc,
                    )
                else:
                    item.status = "failed"
                    item.scheduled_at = _next_retry_at(item.attempts)
                    failed += 1
                    logger.warning(
                        "notification delivery failed id=%s attempt=%s next_retry=%s error=%s",
                        item.id,
                        attempt_label,
                        item.scheduled_at.isoformat(),
                        exc,
                    )

        await db.commit()

    result = {
        "provider": provider,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "dead_letter": dead_letter,
    }
    logger.info("deliver_queued_notifications complete: %s", result)
    return result
