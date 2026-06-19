from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.contracts.models import Contract
from app.modules.contracts.schemas import ContractCreate, ContractPatch


def serialize_contract(contract: Contract) -> dict:
    return {
        "id": contract.id,
        "tenant_id": contract.tenant_id,
        "client_id": contract.client_id,
        "client_name": contract.client_name,
        "contract_reference": contract.contract_reference,
        "title": contract.title,
        "status": contract.status,
        "service_type": contract.service_type,
        "billing_cycle": contract.billing_cycle,
        "billing_basis": contract.billing_basis,
        "currency": contract.currency,
        "default_unit_price": contract.default_unit_price,
        "requires_load_permit": contract.requires_load_permit,
        "requires_delivery_proof": contract.requires_delivery_proof,
        "requires_cargo_manifest_for_manufactured_goods": (
            contract.requires_cargo_manifest_for_manufactured_goods
        ),
        "pricing_rules": contract.pricing_rules,
        "starts_at": contract.starts_at,
        "ends_at": contract.ends_at,
        "notes": contract.notes,
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }


async def list_contracts(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    client_id: UUID | None = None,
    client_name: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Contract).where(Contract.tenant_id == tenant_id)

    if client_id:
        query = query.where(Contract.client_id == client_id)
    if client_name:
        query = query.where(Contract.client_name.ilike(f"%{client_name}%"))
    if status_filter:
        query = query.where(Contract.status == status_filter)

    result = await db.execute(
        query.order_by(Contract.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_contract(contract) for contract in result.scalars()]


async def create_contract(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ContractCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    # Validate that at least one of client_id or client_name is provided
    if not payload.client_id and not payload.client_name:
        raise ApiError(
            "client_required",
            "Seleccione um cliente ou forneça o nome do cliente.",
            status_code=422,
        )

    existing = await db.scalar(
        select(Contract).where(
            Contract.tenant_id == tenant_id,
            Contract.contract_reference == payload.contract_reference,
        )
    )
    if existing:
        raise ApiError(
            "contract_reference_exists",
            "Contract reference already exists for this tenant.",
            status_code=status.HTTP_409_CONFLICT,
            details={"contract_reference": payload.contract_reference},
        )

    # Resolve client_name from client record when client_id is provided
    if payload.client_id:
        from app.modules.clients.models import Client

        client = await db.get(Client, payload.client_id)
        if not client or client.tenant_id != tenant_id:
            raise ApiError("client_not_found", "Cliente não encontrado.", status_code=404)
        client_name_to_use = client.trading_name
    else:
        client_name_to_use = payload.client_name

    data = payload.model_dump(exclude={"client_name"})
    contract = Contract(tenant_id=tenant_id, client_name=client_name_to_use, **data)
    db.add(contract)
    await db.flush()
    await db.refresh(contract)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="contract.created",
        entity_type="contract",
        entity_id=contract.id,
        new_values=serialize_contract(contract),
    )
    await db.commit()
    await db.refresh(contract)
    return serialize_contract(contract)


async def get_contract(db: AsyncSession, tenant_id: UUID, contract_id: UUID) -> dict:
    contract = await db.get(Contract, contract_id)
    if not contract or contract.tenant_id != tenant_id:
        raise ApiError("contract_not_found", "Contract not found.", status_code=404)
    return serialize_contract(contract)


async def patch_contract(
    db: AsyncSession,
    tenant_id: UUID,
    contract_id: UUID,
    payload: ContractPatch,
    *,
    actor_id: UUID | None = None,
) -> dict:
    contract = await db.get(Contract, contract_id)
    if not contract or contract.tenant_id != tenant_id:
        raise ApiError("contract_not_found", "Contract not found.", status_code=404)

    old_values = serialize_contract(contract)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)

    await db.flush()
    await db.refresh(contract)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="contract.updated",
        entity_type="contract",
        entity_id=contract.id,
        old_values=old_values,
        new_values=serialize_contract(contract),
    )
    await db.commit()
    await db.refresh(contract)
    return serialize_contract(contract)


# ── SM-02: Contract State Machine ────────────────────────────────────────────

_CONTRACT_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active"},
    "active": {"paused", "expired", "terminated"},
    "paused": {"active", "expired", "terminated"},
    "expired": {"active", "terminated"},  # active = renew with new ends_at
    "terminated": set(),  # terminal
}


async def transition_contract(
    db: AsyncSession,
    *,
    contract: Contract,
    new_status: str,
    user_id: UUID,
    tenant_id: UUID,
    termination_reason: str | None = None,
    new_ends_at: datetime | None = None,
) -> Contract:
    """Guard-enforced state transition for Contract (SM-02).

    Raises ApiError(409) for invalid transitions.
    All transitions are recorded in audit_log within the same transaction.
    """
    allowed = _CONTRACT_VALID_TRANSITIONS.get(contract.status, set())
    if new_status not in allowed:
        raise ApiError(
            "invalid_state_transition",
            f"Contract cannot transition from '{contract.status}' to '{new_status}'",
            status_code=409,
        )
    if new_status == "terminated" and not termination_reason:
        raise ApiError(
            "termination_reason_required",
            "termination_reason is required when terminating a contract",
            status_code=422,
        )

    old_status = contract.status
    contract.status = new_status
    now = datetime.now(UTC)

    if new_status == "paused":
        contract.paused_at = now
    elif new_status == "active" and old_status == "paused":
        contract.paused_at = None
    elif new_status == "active" and old_status == "expired":
        # Renew: must provide new ends_at
        if not new_ends_at:
            raise ApiError(
                "ends_at_required",
                "new_ends_at is required when renewing an expired contract",
                status_code=422,
            )
        contract.ends_at = new_ends_at
        contract.renewed_at = now
    elif new_status == "terminated":
        contract.terminated_at = now
        contract.termination_reason = termination_reason

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action=f"contract.{new_status}",
        entity_type="contract",
        entity_id=contract.id,
        user_id=user_id,
        old_values={"status": old_status},
        new_values={"status": new_status},
    )
    db.add(contract)
    return contract


async def renew_contract(
    db: AsyncSession,
    *,
    contract_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    new_ends_at: datetime,
) -> Contract:
    """SM-02: Renew an expired contract by extending ends_at and setting status='active'."""
    contract = await db.get(Contract, contract_id)
    if not contract or contract.tenant_id != tenant_id:
        raise ApiError("contract_not_found", "Contract not found", status_code=404)
    return await transition_contract(
        db,
        contract=contract,
        new_status="active",
        user_id=user_id,
        tenant_id=tenant_id,
        new_ends_at=new_ends_at,
    )
