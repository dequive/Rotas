import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Account(Base):
    """
    Plano de Contas (Chart of Accounts).
    Exemplo: 41 - Fornecedores (Liability), 12 - Depósitos à Ordem (Asset).
    """

    __tablename__ = "accounting_accounts"
    __table_args__ = (
        Index("ix_accounting_accounts_tenant_code", "tenant_id", "code", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False) # Asset, Liability, Equity, Revenue, Expense
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounting_accounts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class JournalEntry(Base):
    """
    Cabeçalho do Lançamento no Diário.
    É a representação contabilística de um evento (ex: Fecho de Fatura, Pagamento).
    """

    __tablename__ = "accounting_journal_entries"
    __table_args__ = (
        Index("ix_accounting_journal_entries_tenant_date", "tenant_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    journal_type: Mapped[str] = mapped_column(String(10), default="OD", nullable=False) # VEN, COM, TES, OD
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True) # Ex: "Fatura PUMA-102"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_type: Mapped[str | None] = mapped_column(String(100), nullable=True) # Ex: SupplierInvoice
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False) # draft, posted, reversed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    items: Mapped[list["JournalItem"]] = relationship(
        "JournalItem", back_populates="journal_entry", cascade="all, delete-orphan"
    )


class JournalItem(Base):
    """
    Partidas (Lançamentos detalhados do Diário).
    Para cada JournalEntry, a soma dos debitos tem de igualar a soma dos créditos nestas linhas.
    """

    __tablename__ = "accounting_journal_items"
    __table_args__ = (
        CheckConstraint('debit >= 0 AND credit >= 0', name='check_debit_credit_positive'),
        CheckConstraint('debit = 0 OR credit = 0', name='check_mutually_exclusive'),
        CheckConstraint('debit > 0 OR credit > 0', name='check_not_both_zero'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounting_journal_entries.id"), index=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("accounting_accounts.id"), index=True, nullable=False
    )
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    
    # Tags Analíticas para Activity Based Costing / TCO
    third_party_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("third_parties.id"), index=True, nullable=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("vehicles.id"), index=True, nullable=True
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("trips.id"), index=True, nullable=True
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_orders.id"), index=True, nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="items")
