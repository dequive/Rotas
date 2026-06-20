import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "contract_reference",
            name="uq_contracts_tenant_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    # Phase 5 Plan 02: client_id FK added via migration e5f6a7b8c9d0 (migration b);
    # nullable until backfill
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"), index=True, nullable=True
    )
    client_name: Mapped[str] = mapped_column(String(160), index=True)
    contract_reference: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    service_type: Mapped[str] = mapped_column(String(60), default="cargo_transport")
    billing_cycle: Mapped[str] = mapped_column(String(30), default="monthly")
    billing_basis: Mapped[str] = mapped_column(String(40), default="trip")
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    default_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    requires_load_permit: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_delivery_proof: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_cargo_manifest_for_manufactured_goods: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    pricing_rules: Mapped[dict | None] = mapped_column(JSON)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # SM-02: State machine audit fields
    # Valid status values: draft | active | paused | expired | terminated
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    client_nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
