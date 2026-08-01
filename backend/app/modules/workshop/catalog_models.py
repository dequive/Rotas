import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ServiceCatalogItem(Base):
    """Catálogo de Serviços da Oficina (preços base, tempos standard, mão de obra)."""

    __tablename__ = "service_catalog_items"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_service_catalog_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)  # ex: "SERV-001"
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60), default="geral", index=True)
    # mecanica | electricidade | pintura | pneus | ac | geral
    standard_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    base_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    includes_parts: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
