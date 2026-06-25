from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


# ── Taxonomy ──────────────────────────────────────────────────────────────────

class TaxonomyDomain(Base):
    __tablename__ = "taxonomy_domains"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxonomyCaseType(Base):
    __tablename__ = "taxonomy_case_types"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    domain_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_domains.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="open")
    sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxonomyType(Base):
    __tablename__ = "taxonomy_types"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    domain_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_domains.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxonomyTypePromotion(Base):
    __tablename__ = "taxonomy_type_promotions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    type_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_types.id"), nullable=False)
    case_type_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_case_types.id"), nullable=False)
    min_severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="alta")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Entity catalog ────────────────────────────────────────────────────────────

class EntityCatalog(Base):
    __tablename__ = "entity_catalogs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityInstance(Base):
    __tablename__ = "entity_instances"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    catalog_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entity_catalogs.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Occurrences ───────────────────────────────────────────────────────────────

class Occurrence(Base):
    __tablename__ = "occurrences"
    __table_args__ = (
        # Scoped to tenant so different tenants can reuse the same key string.
        # Partial index (WHERE idempotency_key IS NOT NULL) mirrors the SQL migration.
        UniqueConstraint("tenant_id", "idempotency_key", name="ux_occurrences_idem_key"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    numero: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_types.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reported_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), nullable=True)
    supersedes_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("occurrences.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class OccurrenceLink(Base):
    __tablename__ = "occurrence_links"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    occurrence_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("occurrences.id"), nullable=False)
    instance_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entity_instances.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="sujeito")
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    occurrence_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("occurrences.id"), nullable=True)
    case_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Cases ─────────────────────────────────────────────────────────────────────

class Case(Base):
    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reference: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    case_type_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_case_types.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="open")
    assignee_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseOccurrence(Base):
    __tablename__ = "case_occurrences"
    __table_args__ = (UniqueConstraint("case_id", "occurrence_id"),)

    case_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    occurrence_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("occurrences.id"), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseTransitionRule(Base):
    __tablename__ = "case_transition_rules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    case_type_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("taxonomy_case_types.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    required_fields: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    required_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseTransition(Base):
    __tablename__ = "case_transitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="ux_case_transitions_idem_key"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Activities & Notes ────────────────────────────────────────────────────────

class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    transition_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("case_transitions.id"), nullable=True)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    occurrence_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("occurrences.id"), nullable=True)
    case_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    author_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
