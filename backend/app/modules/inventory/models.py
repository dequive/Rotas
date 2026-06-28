import uuid
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ItemCategory(Base):
    __tablename__ = "item_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("item_categories.id", ondelete="SET NULL"), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Ex: L (Litros), UN (Unidades), KG
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False, default="UN")
    
    # Financial and Tracking
    current_stock: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"))
    average_unit_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"))
    
    category: Mapped[Optional["ItemCategory"]] = relationship()


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    
    # 'IN' (Entrada/Compra), 'OUT' (Saída/Consumo), 'ADJ' (Ajuste/Quebra)
    movement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # O valor unitário no momento do movimento. 
    # Em Entradas ('IN'), este é o preço de compra e afeta a Média.
    # Em Saídas ('OUT'), este copia o `average_unit_cost` do Item naquele instante.
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    total_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Link to a Document (Factura de Compra, Guia de Remessa, Ordem de Oficina)
    reference_doc: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Quem autorizou ou fez o lançamento na plataforma
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    item: Mapped["Item"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship()
