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
    client_name: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Contract).where(Contract.tenant_id == tenant_id)

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

    contract = Contract(tenant_id=tenant_id, **payload.model_dump())
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
