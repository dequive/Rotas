import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(40), default="trial")
    max_vehicles: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    max_drivers: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_number: Mapped[str | None] = mapped_column(String(40))
    timezone: Mapped[str] = mapped_column(String(80), default="Africa/Maputo")
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    compliance_policy: Mapped[dict | None] = mapped_column(JSON)
    nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
