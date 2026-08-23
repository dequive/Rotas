from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import CARGO_WRITE, require_permission
from app.modules.cargo import schemas, service
from app.modules.cargo.schemas import DeliveryProofRejectRequest

router = APIRouter(prefix="/trips/{trip_id}", tags=["cargo"])


@router.post("/load-permits")
async def create_load_permit(
    request: Request,
    trip_id: UUID,
    payload: schemas.LoadPermitCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/cargo-manifest")
async def create_cargo_manifest(
    request: Request,
    trip_id: UUID,
    payload: schemas.CargoManifestCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/transport-documents")
async def create_transport_document(
    request: Request,
    trip_id: UUID,
    payload: schemas.TransportDocumentCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/delivery-proof")
async def create_delivery_proof(
    request: Request,
    trip_id: UUID,
    payload: schemas.DeliveryProofCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/delivery-proof/{proof_id}/validate")
async def validate_delivery_proof(
    request: Request,
    trip_id: UUID,
    proof_id: UUID,
    payload: schemas.ValidateDeliveryProofRequest,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/delivery-proof/{proof_id}/dispute")
async def dispute_delivery_proof(
    request: Request,
    trip_id: UUID,
    proof_id: UUID,
    payload: schemas.DisputeDeliveryProofRequest,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/delivery-proof/{proof_id}/resolve-dispute")
async def resolve_delivery_proof_dispute(
    request: Request,
    trip_id: UUID,
    proof_id: UUID,
    payload: schemas.ResolveDeliveryProofDisputeRequest,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.patch("/delivery-proof/{proof_id}/accept", summary="Accept delivery proof (SM-03)")
async def accept_delivery_proof_endpoint(
    request: Request,
    trip_id: UUID,
    proof_id: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
):
    from app.modules.cargo.service import accept_delivery_proof

    proof = await accept_delivery_proof(
        db,
        proof_id=proof_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )
    await db.commit()
    await db.refresh(proof)
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return proof


@router.patch("/delivery-proof/{proof_id}/reject", summary="Reject delivery proof (SM-03)")
async def reject_delivery_proof_endpoint(
    request: Request,
    trip_id: UUID,
    proof_id: UUID,
    body: DeliveryProofRejectRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
):
    from app.modules.cargo.service import reject_delivery_proof

    proof = await reject_delivery_proof(
        db,
        proof_id=proof_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        rejection_reason=body.rejection_reason,
    )
    await db.commit()
    await db.refresh(proof)
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return proof


# ── OPDOC-02: Guia de Remessa ─────────────────────────────────────────────────


@router.post("/guia-remessa", status_code=201)
async def create_guia_remessa(
    request: Request,
    trip_id: UUID,
    payload: schemas.GuiaRemessaCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """OPDOC-02: Create a Guia de Remessa and generate its PDF. Returns document + pdf_url."""
    res = await service.create_guia_remessa(
        db,
        principal.tenant_id,
        trip_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


# ── OPDOC-03: Carta de Porte Internacional ────────────────────────────────────


@router.post("/carta-porte-internacional", status_code=201)
async def create_carta_porte(
    request: Request,
    trip_id: UUID,
    payload: schemas.CartaPorteCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """OPDOC-03: Create a Carta de Porte Internacional (bilingual PT/EN PDF).

    Returns document + pdf_url.
    """
    res = await service.create_carta_porte(
        db,
        principal.tenant_id,
        trip_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


# ── OPDOC-04: DAV ─────────────────────────────────────────────────────────────


@router.post("/dav", status_code=201)
async def create_dav(
    request: Request,
    trip_id: UUID,
    payload: schemas.DAVCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """OPDOC-04: Record a DAV (Declaração de Aprovação de Viagem). Digital record only — no PDF."""
    res = await service.create_dav(
        db,
        principal.tenant_id,
        trip_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


# ── OPDOC-05: Document checklist ──────────────────────────────────────────────


@router.post("/declaracao-carga-perigosa", status_code=201)
async def create_declaracao_carga_perigosa(
    request: Request,
    trip_id: UUID,
    payload: schemas.DeclaracaoCargaPerisgosaCreate,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Declaração de Carga Perigosa — digital record for hazmat trips (no PDF)."""
    res = await service.create_declaracao_carga_perigosa(
        db,
        principal.tenant_id,
        trip_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/document-checklist", response_model=schemas.TripDocumentChecklistRead)
async def get_document_checklist(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(CARGO_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Return the canonical dispatch requirements and their present/missing state."""
    return await service.get_document_checklist(
        db,
        principal.tenant_id,
        trip_id,
    )
