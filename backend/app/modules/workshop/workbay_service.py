from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.workshop.workbay_models import WorkBay
from app.modules.workshop.workbay_schemas import WorkBayCreate, WorkBayUpdate


def serialize_work_bay(bay: WorkBay) -> dict:
    return {
        "id": bay.id,
        "tenant_id": bay.tenant_id,
        "name": bay.name,
        "category": bay.category,
        "is_active": bay.is_active,
        "created_at": bay.created_at,
    }


async def create_work_bay(
    db: AsyncSession,
    tenant_id: UUID,
    payload: WorkBayCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    bay = WorkBay(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        category=payload.category,
        is_active=payload.is_active,
    )
    db.add(bay)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_bay.created",
        entity_type="work_bay",
        entity_id=bay.id,
        new_values={"name": bay.name, "category": bay.category},
    )
    await db.commit()
    await db.refresh(bay)
    return serialize_work_bay(bay)


async def list_work_bays(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    is_active: bool | None = None,
) -> list[dict]:
    query = select(WorkBay).where(WorkBay.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(WorkBay.is_active == is_active)

    res = await db.execute(query.order_by(WorkBay.name.asc()))
    return [serialize_work_bay(b) for b in res.scalars().all()]


async def update_work_bay(
    db: AsyncSession,
    tenant_id: UUID,
    bay_id: UUID,
    payload: WorkBayUpdate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    bay = await db.get(WorkBay, bay_id)
    if not bay or bay.tenant_id != tenant_id:
        raise ApiError("bay_not_found", "Work bay not found.", status_code=404)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(bay, k, v)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_bay.updated",
        entity_type="work_bay",
        entity_id=bay.id,
        new_values=data,
    )
    await db.commit()
    await db.refresh(bay)
    return serialize_work_bay(bay)
