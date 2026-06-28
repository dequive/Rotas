from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_tenant_caches

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import BILLING_ISSUE, BILLING_READ, BILLING_WRITE, require_permission
from app.modules.contracts import schemas, service
from app.modules.contracts.models import Contract

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/")
async def list_contracts(
    principal: Annotated[Principal, Depends(require_permission(BILLING_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    client_id: UUID | None = None,
    client_name: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_contracts(
        db,
        principal.tenant_id,
        client_id=client_id,
        client_name=client_name,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.post("/")
async def create_contract(
    request: Request,
    payload: schemas.ContractCreate,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="contracts.create",
        entity_type="contract",
        payload=payload,
        handler=lambda: service.create_contract(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{contract_id}")
async def get_contract(
    contract_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(BILLING_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_contract(db, principal.tenant_id, contract_id)


@router.patch("/{contract_id}")
async def patch_contract(
    request: Request,
    contract_id: UUID,
    payload: schemas.ContractPatch,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.patch_contract(
        db,
        principal.tenant_id,
        contract_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


# ── SM-02: Contract state machine endpoint ───────────────────────────────────


@router.patch("/{contract_id}/status", summary="Transition contract status (SM-02)")
async def transition_contract_status(
    request: Request,
    contract_id: UUID,
    payload: schemas.ContractTransitionRequest,
    principal: Annotated[Principal, Depends(require_permission(BILLING_ISSUE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """SM-02: Transition Contract between allowed states.

    Actions and resulting status:
    - activate  → active   (from draft)
    - pause     → paused   (from active)
    - resume    → active   (from paused)
    - expire    → expired  (manual; cron also does this automatically)
    - terminate → terminated (requires termination_reason)
    - renew     → active   (from expired; requires new_ends_at)

    Returns HTTP 409 for invalid transitions.
    """
    action_to_status = {
        "activate": "active",
        "pause": "paused",
        "resume": "active",
        "expire": "expired",
        "terminate": "terminated",
        "renew": "active",
    }
    new_status = action_to_status[payload.action]
    contract = await db.get(Contract, contract_id)
    if not contract or contract.tenant_id != principal.tenant_id:
        raise ApiError("contract_not_found", "Contract not found", status_code=404)
    updated = await service.transition_contract(
        db,
        contract=contract,
        new_status=new_status,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        termination_reason=payload.termination_reason,
        new_ends_at=payload.new_ends_at,
    )
    await db.commit()
    await db.refresh(updated)
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return service.serialize_contract(updated)


@router.get("/{contract_id}/tariffs")
async def list_contract_tariffs(
    contract_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(BILLING_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_contract_tariffs(db, principal.tenant_id, contract_id)


@router.post("/{contract_id}/tariffs")
async def create_contract_tariff(
    request: Request,
    contract_id: UUID,
    payload: schemas.ContractTariffCreate,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="contract_tariffs.create",
        entity_type="contract_tariff",
        payload=payload,
        handler=lambda: service.create_contract_tariff(
            db,
            principal.tenant_id,
            contract_id,
            payload,
            actor_id=principal.user_id,
        ),
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.patch("/{contract_id}/tariffs/{tariff_id}")
async def update_contract_tariff(
    request: Request,
    contract_id: UUID,
    tariff_id: UUID,
    payload: schemas.ContractTariffPatch,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.update_contract_tariff(
        db,
        principal.tenant_id,
        contract_id,
        tariff_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.delete("/{contract_id}/tariffs/{tariff_id}")
async def delete_contract_tariff(
    request: Request,
    contract_id: UUID,
    tariff_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await service.delete_contract_tariff(
        db,
        principal.tenant_id,
        contract_id,
        tariff_id,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return {"status": "success"}
