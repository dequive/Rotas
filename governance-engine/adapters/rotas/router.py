from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.rotas.schemas import (
    RotasBootstrapRequest,
    RotasEntitySyncRequest,
    RotasEntitySyncResponse,
    RotasEventPush,
    RotasEventPushResponse,
)
from adapters.rotas.service import RotasAdapterService
from core.auth import Principal
from core.deps import get_session, require_scope

router = APIRouter(prefix="/adapters/rotas", tags=["adapter:rotas"])


@router.post("/bootstrap", status_code=200)
async def bootstrap(
    body: RotasBootstrapRequest,
    principal: Principal = Depends(require_scope("adapter:rotas")),
    db: AsyncSession = Depends(get_session),
):
    svc = RotasAdapterService(db, UUID(principal.tenant_id), UUID(principal.actor_id))
    return await svc.bootstrap()


@router.post("/entities/sync", status_code=200, response_model=RotasEntitySyncResponse)
async def sync_entities(
    body: RotasEntitySyncRequest,
    principal: Principal = Depends(require_scope("adapter:rotas")),
    db: AsyncSession = Depends(get_session),
):
    svc = RotasAdapterService(db, UUID(principal.tenant_id), UUID(principal.actor_id))
    ids = await svc.sync_entities(body.entities)
    return RotasEntitySyncResponse(synced=len(ids), entity_ids=ids)


@router.post("/events", status_code=201, response_model=RotasEventPushResponse)
async def push_event(
    body: RotasEventPush,
    principal: Principal = Depends(require_scope("adapter:rotas")),
    db: AsyncSession = Depends(get_session),
):
    svc = RotasAdapterService(db, UUID(principal.tenant_id), UUID(principal.actor_id))
    return await svc.push_event(body)
