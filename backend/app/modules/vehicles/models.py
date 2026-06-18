import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("tenant_id", "plate", name="uq_vehicles_tenant_plate"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    plate: Mapped[str] = mapped_column(String(40), index=True)
    chassis: Mapped[str | None] = mapped_column(String(80))
    brand: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(30), default="pesado")
    status: Mapped[str] = mapped_column(String(30), default="active")
    current_km: Mapped[int] = mapped_column(Integer, default=0)
    fuel_type: Mapped[str] = mapped_column(String(30), default="gasoleo")
    documents: Mapped[dict | None] = mapped_column(JSON)
    qr_code_hash: Mapped[str | None] = mapped_column(String(255), index=True)
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    avg_consumption_target: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fuel_limit_daily: Mapped[float | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
