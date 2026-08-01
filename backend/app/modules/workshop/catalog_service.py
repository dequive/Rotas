from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.workshop.catalog_models import ServiceCatalogItem
from app.modules.workshop.catalog_schemas import CatalogItemCreate, CatalogItemUpdate


def serialize_catalog_item(item: ServiceCatalogItem) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "code": item.code,
        "name": item.name,
        "category": item.category,
        "standard_duration_minutes": item.standard_duration_minutes,
        "base_price": float(item.base_price),
        "includes_parts": item.includes_parts,
        "is_active": item.is_active,
        "notes": item.notes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


async def create_catalog_item(
    db: AsyncSession,
    tenant_id: UUID,
    payload: CatalogItemCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    code_exists = await db.scalar(
        select(ServiceCatalogItem.id).where(
            ServiceCatalogItem.tenant_id == tenant_id,
            ServiceCatalogItem.code == payload.code.strip(),
        )
    )
    if code_exists:
        raise ApiError("code_already_exists", "Catalog code already exists.", status_code=409)

    item = ServiceCatalogItem(
        tenant_id=tenant_id,
        code=payload.code.strip(),
        name=payload.name.strip(),
        category=payload.category,
        standard_duration_minutes=payload.standard_duration_minutes,
        base_price=payload.base_price,
        includes_parts=payload.includes_parts,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    db.add(item)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="catalog_item.created",
        entity_type="service_catalog_item",
        entity_id=item.id,
        new_values={"code": item.code, "name": item.name},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_catalog_item(item)


async def list_catalog_items(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    category: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(ServiceCatalogItem).where(ServiceCatalogItem.tenant_id == tenant_id)
    if category:
        query = query.where(ServiceCatalogItem.category == category)
    if is_active is not None:
        query = query.where(ServiceCatalogItem.is_active == is_active)

    res = await db.execute(
        query.order_by(ServiceCatalogItem.code.asc()).limit(limit).offset(offset)
    )
    return [serialize_catalog_item(it) for it in res.scalars().all()]


async def update_catalog_item(
    db: AsyncSession,
    tenant_id: UUID,
    item_id: UUID,
    payload: CatalogItemUpdate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    item = await db.get(ServiceCatalogItem, item_id)
    if not item or item.tenant_id != tenant_id:
        raise ApiError("item_not_found", "Catalog item not found.", status_code=404)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="catalog_item.updated",
        entity_type="service_catalog_item",
        entity_id=item.id,
        new_values=data,
    )
    await db.commit()
    await db.refresh(item)
    return serialize_catalog_item(item)
