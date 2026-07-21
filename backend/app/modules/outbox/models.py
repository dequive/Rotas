import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OutboxEvent(Base):
    """Transactional outbox event for the ROTAS -> external systems bridge.

    Persisted in the same transaction as the business write so we never lose
    an event even if the process crashes afterwards. The ARQ drainer job
    picks rows up by ``status='pending' AND next_attempt_at <= now()``,
    ships them to the configured downstream (``governance_engine_url``),
    and either marks them ``sent`` or schedules a backoff retry.

    Tenant isolated via RLS in the same migration that creates the table.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )

    aggregate_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending", index=True
    )
    governance_case_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)