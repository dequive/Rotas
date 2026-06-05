from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import ADMIN_ROLES, DASHBOARD_ROLES, require_roles
from app.core.deps import get_session
from app.modules.operations import schemas, service

router = APIRouter(prefix="/operations", tags=["operations"])


@router.post("/waivers")
async def create_waiver(
    payload: schemas.OperationalWaiverCreate,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="operations.waiver.create",
        entity_type="operational_waiver",
        payload=payload,
        handler=lambda: service.create_waiver(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/waivers")
async def list_waivers(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    status: str | None = None,
    waiver_type: str | None = None,
):
    return await service.list_waivers(
        db,
        principal.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status_filter=status,
        waiver_type=waiver_type,
    )


@router.post("/waivers/{waiver_id}/revoke")
async def revoke_waiver(
    waiver_id: UUID,
    payload: schemas.OperationalWaiverRevokeRequest,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.revoke_waiver(
        db,
        principal.tenant_id,
        waiver_id,
        payload,
        actor_id=principal.user_id,
    )
