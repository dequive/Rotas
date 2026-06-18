from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.cargo import schemas, service
from app.modules.cargo.schemas import DeliveryProofRejectRequest

router = APIRouter(prefix="/trips/{trip_id}", tags=["cargo"])


@router.post("/load-permits")
async def create_load_permit(
    trip_id: UUID,
    payload: schemas.LoadPermitCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.load_permit.create",
        entity_type="load_permit",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_load_permit(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/cargo-manifest")
async def create_cargo_manifest(
    trip_id: UUID,
    payload: schemas.CargoManifestCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.manifest.create",
        entity_type="cargo_manifest",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_cargo_manifest(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/transport-documents")
async def create_transport_document(
    trip_id: UUID,
    payload: schemas.TransportDocumentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.transport_document.create",
        entity_type="transport_document",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_transport_document(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/delivery-proof")
async def create_delivery_proof(
    trip_id: UUID,
    payload: schemas.DeliveryProofCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.delivery_proof.create",
        entity_type="delivery_proof",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_delivery_proof(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/delivery-proof/{proof_id}/validate")
async def validate_delivery_proof(
    trip_id: UUID,
    proof_id: UUID,
    payload: schemas.ValidateDeliveryProofRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.delivery_proof.validate",
        entity_type="delivery_proof",
        payload={"trip_id": trip_id, "proof_id": proof_id, **payload.model_dump()},
        handler=lambda: service.validate_delivery_proof(
            db,
            principal.tenant_id,
            trip_id,
            proof_id,
            principal.user_id,
            payload,
        ),
    )


@router.post("/delivery-proof/{proof_id}/dispute")
async def dispute_delivery_proof(
    trip_id: UUID,
    proof_id: UUID,
    payload: schemas.DisputeDeliveryProofRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.delivery_proof.dispute",
        entity_type="delivery_proof",
        payload={"trip_id": trip_id, "proof_id": proof_id, **payload.model_dump()},
        handler=lambda: service.dispute_delivery_proof(
            db,
            principal.tenant_id,
            trip_id,
            proof_id,
            principal.user_id,
            payload,
        ),
    )


@router.post("/delivery-proof/{proof_id}/resolve-dispute")
async def resolve_delivery_proof_dispute(
    trip_id: UUID,
    proof_id: UUID,
    payload: schemas.ResolveDeliveryProofDisputeRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="cargo.delivery_proof.resolve_dispute",
        entity_type="delivery_proof",
        payload={"trip_id": trip_id, "proof_id": proof_id, **payload.model_dump()},
        handler=lambda: service.resolve_delivery_proof_dispute(
            db,
            principal.tenant_id,
            trip_id,
            proof_id,
            principal.user_id,
            payload,
        ),
    )


@router.patch("/delivery-proof/{proof_id}/accept", summary="Accept delivery proof (SM-03)")
async def accept_delivery_proof_endpoint(
    trip_id: UUID,
    proof_id: UUID,
    db: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_roles("owner", "admin", "manager")),
):
    from app.modules.cargo.service import accept_delivery_proof
    proof = await accept_delivery_proof(
        db, proof_id=proof_id,
        tenant_id=principal.tenant_id, user_id=principal.user_id,
    )
    await db.commit()
    await db.refresh(proof)
    return proof


@router.patch("/delivery-proof/{proof_id}/reject", summary="Reject delivery proof (SM-03)")
async def reject_delivery_proof_endpoint(
    trip_id: UUID,
    proof_id: UUID,
    body: DeliveryProofRejectRequest,
    db: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_roles("owner", "admin", "manager")),
):
    from app.modules.cargo.service import reject_delivery_proof
    proof = await reject_delivery_proof(
        db, proof_id=proof_id,
        tenant_id=principal.tenant_id, user_id=principal.user_id,
        rejection_reason=body.rejection_reason,
    )
    await db.commit()
    await db.refresh(proof)
    return proof
