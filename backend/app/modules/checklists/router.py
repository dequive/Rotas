from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.checklists import schemas, service

router = APIRouter(tags=["checklists"])


@router.get("/checklist-templates")
async def list_templates(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    type: str | None = None,
    is_active: bool | None = True,
):
    return await service.list_templates(
        db,
        principal.tenant_id,
        type_filter=type,
        is_active=is_active,
    )


@router.post("/checklist-templates")
async def create_template(
    payload: schemas.ChecklistTemplateCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="checklists.template.create",
        entity_type="checklist_template",
        payload=payload,
        handler=lambda: service.create_template(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/checklists")
async def list_checklists(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_checklists(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )


@router.post("/checklists")
async def create_checklist(
    payload: schemas.ChecklistCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
        device_id=principal.device_id,
        idempotency_key=idempotency_key,
        operation="checklists.create",
        entity_type="checklist",
        payload=payload,
        handler=lambda: service.create_checklist(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
            driver_actor_id=principal.driver_id,
        ),
    )


@router.patch("/checklists/{checklist_id}")
async def patch_checklist(
    checklist_id: UUID,
    payload: schemas.ChecklistPatch,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_checklist(
        db,
        principal.tenant_id,
        checklist_id,
        payload,
        actor_id=principal.user_id,
        driver_actor_id=principal.driver_id,
    )


@router.post("/checklists/{checklist_id}/complete")
async def complete_checklist(
    checklist_id: UUID,
    payload: schemas.CompleteChecklistRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.complete_checklist(
        db,
        principal.tenant_id,
        checklist_id,
        payload,
        actor_id=principal.user_id,
        driver_actor_id=principal.driver_id,
    )


@router.post("/checklists/{checklist_id}/resolve-failure")
async def resolve_checklist_failure(
    checklist_id: UUID,
    payload: schemas.ResolveChecklistFailureRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.resolve_checklist_failure(
        db,
        principal.tenant_id,
        checklist_id,
        payload,
        actor_id=principal.user_id,
    )
