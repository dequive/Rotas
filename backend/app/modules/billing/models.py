import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BillingDocument(Base):
    __tablename__ = "billing_documents"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="chk_billing_documents_subtotal_non_negative"),
        CheckConstraint("tax_amount >= 0", name="chk_billing_documents_tax_non_negative"),
        CheckConstraint("total_amount >= 0", name="chk_billing_documents_total_non_negative"),
        CheckConstraint(
            "iva_rate IS NULL OR (iva_rate >= 0 AND iva_rate <= 1)",
            name="chk_billing_documents_iva_rate_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    # Phase 5 Plan 02: client_id FK added via migration e5f6a7b8c9d0 (migration b)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"), index=True, nullable=True
    )
    client_name: Mapped[str] = mapped_column(String(160), index=True)
    contract_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    billing_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 5 Plan 02: due_date added via migration e5f6a7b8c9d0; aging uses stored date (not derived)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # SM-01: State machine audit fields
    overdue_since_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    invoice_number: Mapped[str | None] = mapped_column(String(12), nullable=True)
    iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillingItem(Base):
    __tablename__ = "billing_items"
    __table_args__ = (
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="chk_billing_items_quantity_non_negative",
        ),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="chk_billing_items_unit_price_non_negative",
        ),
        CheckConstraint("amount >= 0", name="chk_billing_items_amount_non_negative"),
        CheckConstraint(
            "iva_rate IS NULL OR (iva_rate >= 0 AND iva_rate <= 1)",
            name="chk_billing_items_iva_rate_range",
        ),
        CheckConstraint(
            "iva_amount IS NULL OR iva_amount >= 0",
            name="chk_billing_items_iva_amount_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    billing_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_documents.id"), index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    load_permit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("load_permits.id"))
    cargo_manifest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cargo_manifests.id"))
    transport_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transport_documents.id")
    )
    delivery_proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_proofs.id"))
    client_reference: Mapped[str | None] = mapped_column(String(120))
    origin: Mapped[str | None] = mapped_column(String(160))
    destination: Mapped[str | None] = mapped_column(String(160))
    district: Mapped[str | None] = mapped_column(String(120))
    cargo_description: Mapped[str | None] = mapped_column(Text)
    cargo_class: Mapped[str | None] = mapped_column(String(40))
    load_state: Mapped[str | None] = mapped_column(String(40))
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    iva_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportJob(Base):
    """Tracks async billing export jobs (PDF/XLSX) processed by the ARQ worker."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_export_jobs_tenant_entity_type", "tenant_id", "entity_id", "job_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'billing_pdf', 'billing_xlsx'
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # billing_document_id
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued|processing|done|failed
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # file_path is kept for backward compatibility with existing download endpoints
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id"), nullable=True
    )  # Populated by ARQ worker after storage.py refactor (INFRA-02)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClientPayment(Base):
    """Phase 5 scaffold — service and router implemented in Phase 6.

    Tracks payments received from clients. billing_document_id is nullable to support
    advance payments (no invoice at creation time). Voided payments are never hard-deleted —
    status transitions to 'voided' with audit trail preserved.
    """

    __tablename__ = "client_payments"
    __table_args__ = (
        Index("ix_client_payments_tenant_client", "tenant_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    # Nullable — advance payments have no invoice at creation time
    billing_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing_documents.id"), index=True, nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    value_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payment_method: Mapped[str] = mapped_column(String(40))  # bank_transfer|cheque|cash
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(20), default="confirmed")  # confirmed|voided
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    void_reason: Mapped[str | None] = mapped_column(Text())
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaymentAllocation(Base):
    """Junction table linking client_payments to billing_documents. Phase 5 scaffold.

    Created in Phase 5 (not Phase 7) to avoid high-risk retrofit migration after payment
    rows exist. Phase 6 service layer will write allocations when payments are confirmed.
    """

    __tablename__ = "payment_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client_payments.id"), index=True)
    billing_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_documents.id"), index=True
    )
    amount_applied: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
