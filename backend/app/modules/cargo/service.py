from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.cargo.models import CargoManifest, DeliveryProof, LoadPermit, TransportDocument
from app.modules.cargo.schemas import (
    CargoManifestCreate,
    DeliveryProofCreate,
    DisputeDeliveryProofRequest,
    LoadPermitCreate,
    ResolveDeliveryProofDisputeRequest,
    TransportDocumentCreate,
    ValidateDeliveryProofRequest,
)
from app.modules.operational_exceptions.service import ensure_exception, resolve_active_exceptions
from app.modules.trips.models import Trip

_DELIVERY_PROOF_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"accepted", "rejected"},
    "rejected": {"disputed"},
    "disputed": {"resolved"},
    "accepted": set(),  # terminal
    "resolved": set(),  # terminal
}


def now_utc() -> datetime:
    return datetime.now(UTC)


async def _require_trip(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> Trip:
    trip = await db.get(Trip, trip_id)
    if not trip or trip.tenant_id != tenant_id:
        raise ApiError("trip_not_found", "Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
    return trip


def _audit_load_permit(permit: LoadPermit) -> dict:
    return {
        "trip_id": permit.trip_id,
        "contract_id": permit.contract_id,
        "client_name": permit.client_name,
        "client_reference": permit.client_reference,
        "permit_number": permit.permit_number,
        "issuer_type": permit.issuer_type,
        "issuer_name": permit.issuer_name,
        "district": permit.district,
        "location_name": permit.location_name,
        "origin": permit.origin,
        "destination": permit.destination,
        "valid_from": permit.valid_from,
        "valid_until": permit.valid_until,
        "leg_type": permit.leg_type,
        "load_state": permit.load_state,
        "file_id": permit.file_id,
        "status": permit.status,
        "notes": permit.notes,
    }


def _audit_cargo_manifest(manifest: CargoManifest) -> dict:
    return {
        "trip_id": manifest.trip_id,
        "contract_id": manifest.contract_id,
        "manifest_number": manifest.manifest_number,
        "issuer_user_id": manifest.issuer_user_id,
        "client_name": manifest.client_name,
        "shipper_name": manifest.shipper_name,
        "recipient_name": manifest.recipient_name,
        "cargo_description": manifest.cargo_description,
        "cargo_type": manifest.cargo_type,
        "cargo_class": manifest.cargo_class,
        "package_count": manifest.package_count,
        "gross_weight": manifest.gross_weight,
        "origin": manifest.origin,
        "destination": manifest.destination,
        "issued_at": manifest.issued_at,
        "file_id": manifest.file_id,
        "status": manifest.status,
    }


def _audit_transport_document(document: TransportDocument) -> dict:
    return {
        "trip_id": document.trip_id,
        "contract_id": document.contract_id,
        "document_type": document.document_type,
        "document_number": document.document_number,
        "issuer": document.issuer,
        "client_name": document.client_name,
        "issued_at": document.issued_at,
        "valid_from": document.valid_from,
        "valid_until": document.valid_until,
        "origin": document.origin,
        "destination": document.destination,
        "district": document.district,
        "location_name": document.location_name,
        "file_id": document.file_id,
        "status": document.status,
        "notes": document.notes,
    }


def _audit_delivery_proof(proof: DeliveryProof) -> dict:
    return {
        "trip_id": proof.trip_id,
        "contract_id": proof.contract_id,
        "load_permit_id": proof.load_permit_id,
        "load_permit_number": proof.load_permit_number,
        "document_number": proof.document_number,
        "proof_type": proof.proof_type,
        "client_type": proof.client_type,
        "receiver_name": proof.receiver_name,
        "receiver_contact": proof.receiver_contact,
        "delivery_location": proof.delivery_location,
        "delivered_at": proof.delivered_at,
        "cargo_condition": proof.cargo_condition,
        "quantity_delivered": proof.quantity_delivered,
        "validation_method": proof.validation_method,
        "file_id": proof.file_id,
        "created_by_driver_id": proof.created_by_driver_id,
        "verified_by_user_id": proof.verified_by_user_id,
        "verified_at": proof.verified_at,
        "status": proof.status,
        "notes": proof.notes,
    }


async def create_load_permit(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: LoadPermitCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)

    # LOAD-02: Hazmat declaration guard
    if trip.is_hazmat and (not trip.hazmat_class or not trip.hazmat_class.strip()):
        raise ApiError(
            "hazmat_declaration_required",
            "Trip is marked as hazmat — hazmat_class must be declared on the trip before creating a Load Permit.",
            status_code=422,
            details={"trip_id": str(trip_id), "is_hazmat": True},
        )

    permit = LoadPermit(tenant_id=tenant_id, trip_id=trip_id, **payload.model_dump())
    db.add(permit)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="cargo.load_permit_created",
        entity_type="load_permit",
        entity_id=permit.id,
        new_values=_audit_load_permit(permit),
    )
    await db.commit()
    await db.refresh(permit)
    return {
        "id": permit.id,
        "trip_id": permit.trip_id,
        "contract_id": permit.contract_id,
        "permit_number": permit.permit_number,
        "issuer_type": permit.issuer_type,
        "status": permit.status,
    }


async def create_cargo_manifest(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: CargoManifestCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_trip(db, tenant_id, trip_id)
    manifest = CargoManifest(tenant_id=tenant_id, trip_id=trip_id, **payload.model_dump())
    db.add(manifest)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="cargo.manifest_created",
        entity_type="cargo_manifest",
        entity_id=manifest.id,
        new_values=_audit_cargo_manifest(manifest),
    )
    await db.commit()
    await db.refresh(manifest)
    return {
        "id": manifest.id,
        "trip_id": manifest.trip_id,
        "manifest_number": manifest.manifest_number,
        "status": manifest.status,
    }


async def create_transport_document(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TransportDocumentCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_trip(db, tenant_id, trip_id)
    document = TransportDocument(tenant_id=tenant_id, trip_id=trip_id, **payload.model_dump())
    db.add(document)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="cargo.transport_document_created",
        entity_type="transport_document",
        entity_id=document.id,
        new_values=_audit_transport_document(document),
    )
    await db.commit()
    await db.refresh(document)
    return {
        "id": document.id,
        "trip_id": document.trip_id,
        "document_type": document.document_type,
        "document_number": document.document_number,
        "status": document.status,
    }


async def create_delivery_proof(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: DeliveryProofCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    old_trip_values = {
        "status": trip.status,
        "actual_arrival": trip.actual_arrival,
        "delivery_file_id": trip.delivery_file_id,
        "cargo_status": trip.cargo_status,
        "billing_status": trip.billing_status,
    }
    proof = DeliveryProof(tenant_id=tenant_id, trip_id=trip_id, **payload.model_dump())
    db.add(proof)

    trip.status = "delivered"
    trip.actual_arrival = proof.delivered_at
    trip.delivery_file_id = proof.file_id
    trip.cargo_status = proof.cargo_condition
    trip.billing_status = "pending_delivery_validation"

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="cargo.delivery_proof_created",
        entity_type="delivery_proof",
        entity_id=proof.id,
        new_values=_audit_delivery_proof(proof),
    )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="trip.delivery_recorded",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_trip_values,
        new_values={
            "status": trip.status,
            "actual_arrival": trip.actual_arrival,
            "delivery_file_id": trip.delivery_file_id,
            "cargo_status": trip.cargo_status,
            "billing_status": trip.billing_status,
        },
    )
    await db.commit()
    await db.refresh(proof)
    await db.refresh(trip)
    return {
        "id": proof.id,
        "trip_id": proof.trip_id,
        "contract_id": proof.contract_id,
        "load_permit_number": proof.load_permit_number,
        "proof_type": proof.proof_type,
        "client_type": proof.client_type,
        "delivered_at": proof.delivered_at,
        "status": proof.status,
        "trip_billing_status": trip.billing_status,
    }


async def accept_delivery_proof(
    db: AsyncSession,
    *,
    proof_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> DeliveryProof:
    """SM-03: Accept delivery proof — sets trip.billing_status = 'billable'."""
    proof = await db.get(DeliveryProof, proof_id)
    if not proof or proof.tenant_id != tenant_id:
        raise ApiError("not_found", "DeliveryProof not found", status_code=404)

    allowed = _DELIVERY_PROOF_VALID_TRANSITIONS.get(proof.status, set())
    if "accepted" not in allowed:
        raise ApiError(
            "invalid_state_transition",
            f"DeliveryProof cannot be accepted from status '{proof.status}'",
            status_code=409,
        )

    now = datetime.utcnow()
    proof.status = "accepted"
    proof.accepted_at = now
    proof.accepted_by = user_id

    # Update trip billing_status to billable
    trip = await db.get(Trip, proof.trip_id)
    if trip:
        trip.billing_status = "billable"
        db.add(trip)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="delivery_proof.accepted",
        entity_type="delivery_proof",
        entity_id=proof.id,
        user_id=user_id,
        old_values={"status": "pending"},
        new_values={"status": "accepted"},
    )
    db.add(proof)
    return proof


async def reject_delivery_proof(
    db: AsyncSession,
    *,
    proof_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    rejection_reason: str,
) -> DeliveryProof:
    """SM-03: Reject delivery proof — creates operational_exception automatically."""
    proof = await db.get(DeliveryProof, proof_id)
    if not proof or proof.tenant_id != tenant_id:
        raise ApiError("not_found", "DeliveryProof not found", status_code=404)

    allowed = _DELIVERY_PROOF_VALID_TRANSITIONS.get(proof.status, set())
    if "rejected" not in allowed:
        raise ApiError(
            "invalid_state_transition",
            f"DeliveryProof cannot be rejected from status '{proof.status}'",
            status_code=409,
        )

    now = datetime.utcnow()
    proof.status = "rejected"
    proof.rejected_at = now
    proof.rejected_by = user_id
    proof.rejection_reason = rejection_reason

    # Create operational_exception automatically (same transaction)
    await ensure_exception(
        db,
        tenant_id=tenant_id,
        entity_type="trip",
        entity_id=proof.trip_id,
        exception_type="delivery_rejected",
        severity="high",
        title="Delivery Proof Rejected",
        message=f"Delivery proof rejected: {rejection_reason}",
        actor_id=user_id,
    )

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="delivery_proof.rejected",
        entity_type="delivery_proof",
        entity_id=proof.id,
        user_id=user_id,
        old_values={"status": "pending"},
        new_values={"status": "rejected", "rejection_reason": rejection_reason},
    )
    db.add(proof)
    return proof


async def validate_delivery_proof(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    proof_id: UUID,
    user_id: UUID | None,
    payload: ValidateDeliveryProofRequest,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    proof = await db.get(DeliveryProof, proof_id)
    if not proof or proof.tenant_id != tenant_id or proof.trip_id != trip_id:
        raise ApiError(
            "delivery_proof_not_found",
            "Delivery proof not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if proof.status in {"validated", "verified"}:
        return {
            "id": proof.id,
            "trip_id": proof.trip_id,
            "status": proof.status,
            "validation_method": proof.validation_method,
            "trip_billing_status": trip.billing_status,
            "billable_at": trip.billable_at,
        }
    if proof.status == "disputed":
        raise ApiError(
            "delivery_proof_disputed",
            "Disputed delivery proof cannot be validated until the dispute is resolved.",
            status_code=status.HTTP_409_CONFLICT,
            details={"proof_id": str(proof.id)},
        )

    old_proof_values = {
        "status": proof.status,
        "verified_by_user_id": proof.verified_by_user_id,
        "verified_at": proof.verified_at,
        "validation_method": proof.validation_method,
        "notes": proof.notes,
    }
    old_trip_values = {"billing_status": trip.billing_status, "billable_at": trip.billable_at}
    proof.status = "validated"
    proof.verified_by_user_id = user_id
    proof.verified_at = now_utc()
    proof.validation_method = payload.validation_method
    if payload.notes:
        proof.notes = payload.notes

    trip.billing_status = "billable" if trip.contract_id else "uncontracted"
    trip.billable_at = proof.verified_at if trip.contract_id else None

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="cargo.delivery_proof_validated",
        entity_type="delivery_proof",
        entity_id=proof.id,
        old_values=old_proof_values,
        new_values={
            "status": proof.status,
            "verified_by_user_id": proof.verified_by_user_id,
            "verified_at": proof.verified_at,
            "validation_method": proof.validation_method,
            "notes": proof.notes,
        },
    )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="trip.billing_readiness_updated",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_trip_values,
        new_values={"billing_status": trip.billing_status, "billable_at": trip.billable_at},
    )
    await db.commit()
    await db.refresh(proof)
    await db.refresh(trip)
    return {
        "id": proof.id,
        "trip_id": proof.trip_id,
        "status": proof.status,
        "validation_method": proof.validation_method,
        "trip_billing_status": trip.billing_status,
        "billable_at": trip.billable_at,
    }


async def dispute_delivery_proof(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    proof_id: UUID,
    user_id: UUID | None,
    payload: DisputeDeliveryProofRequest,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    proof = await db.get(DeliveryProof, proof_id)
    if not proof or proof.tenant_id != tenant_id or proof.trip_id != trip_id:
        raise ApiError(
            "delivery_proof_not_found",
            "Delivery proof not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if trip.billing_status in {"billing_draft", "billed"}:
        raise ApiError(
            "billing_already_started",
            "Delivery proof cannot be disputed after billing has started.",
            status_code=status.HTTP_409_CONFLICT,
            details={"billing_status": trip.billing_status},
        )
    if proof.status == "disputed":
        return {
            "id": proof.id,
            "trip_id": proof.trip_id,
            "status": proof.status,
            "trip_billing_status": trip.billing_status,
            "reason": payload.reason,
        }

    old_proof_values = {
        "status": proof.status,
        "validation_method": proof.validation_method,
        "notes": proof.notes,
    }
    old_trip_values = {"billing_status": trip.billing_status, "billable_at": trip.billable_at}
    proof.status = "disputed"
    proof.validation_method = payload.dispute_type
    proof.notes = payload.notes or payload.reason
    trip.billing_status = "delivery_disputed"
    trip.billable_at = None

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="cargo.delivery_proof_disputed",
        entity_type="delivery_proof",
        entity_id=proof.id,
        old_values=old_proof_values,
        new_values={
            "status": proof.status,
            "validation_method": proof.validation_method,
            "notes": proof.notes,
            "reason": payload.reason,
            "dispute_type": payload.dispute_type,
        },
    )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="trip.delivery_disputed",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_trip_values,
        new_values={"billing_status": trip.billing_status, "billable_at": trip.billable_at},
    )
    await ensure_exception(
        db,
        tenant_id,
        entity_type="delivery_proof",
        entity_id=proof.id,
        exception_type="delivery_proof_disputed",
        severity="high",
        title="Prova de descarga em disputa",
        message="A prova de descarga foi marcada como disputada e bloqueia a cobranca.",
        actor_id=user_id,
        context={
            "trip_id": str(trip.id),
            "contract_id": str(proof.contract_id) if proof.contract_id else None,
            "document_number": proof.document_number,
            "reason": payload.reason,
            "dispute_type": payload.dispute_type,
        },
        source_type="delivery_proof",
        source_id=proof.id,
    )
    await db.commit()
    await db.refresh(proof)
    await db.refresh(trip)
    return {
        "id": proof.id,
        "trip_id": proof.trip_id,
        "status": proof.status,
        "trip_billing_status": trip.billing_status,
        "reason": payload.reason,
    }


async def resolve_delivery_proof_dispute(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    proof_id: UUID,
    user_id: UUID | None,
    payload: ResolveDeliveryProofDisputeRequest,
) -> dict:
    if payload.outcome not in {"validated", "rejected"}:
        raise ApiError(
            "invalid_dispute_outcome",
            "Dispute outcome must be validated or rejected.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed": ["validated", "rejected"], "value": payload.outcome},
        )
    trip = await _require_trip(db, tenant_id, trip_id)
    proof = await db.get(DeliveryProof, proof_id)
    if not proof or proof.tenant_id != tenant_id or proof.trip_id != trip_id:
        raise ApiError(
            "delivery_proof_not_found",
            "Delivery proof not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if proof.status != "disputed":
        raise ApiError(
            "delivery_proof_not_disputed",
            "Only disputed delivery proofs can be resolved through this endpoint.",
            status_code=status.HTTP_409_CONFLICT,
            details={"status": proof.status},
        )

    old_proof_values = {
        "status": proof.status,
        "validation_method": proof.validation_method,
        "verified_by_user_id": proof.verified_by_user_id,
        "verified_at": proof.verified_at,
        "notes": proof.notes,
    }
    old_trip_values = {"billing_status": trip.billing_status, "billable_at": trip.billable_at}

    proof.status = payload.outcome
    proof.validation_method = payload.validation_method
    proof.verified_by_user_id = user_id if payload.outcome == "validated" else None
    proof.verified_at = now_utc() if payload.outcome == "validated" else None
    proof.notes = payload.resolution_notes
    if payload.outcome == "validated":
        trip.billing_status = "billable" if trip.contract_id else "uncontracted"
        trip.billable_at = proof.verified_at if trip.contract_id else None
    else:
        trip.billing_status = "pending_delivery_proof"
        trip.billable_at = None

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="cargo.delivery_dispute_resolved",
        entity_type="delivery_proof",
        entity_id=proof.id,
        old_values=old_proof_values,
        new_values={
            "status": proof.status,
            "validation_method": proof.validation_method,
            "verified_by_user_id": proof.verified_by_user_id,
            "verified_at": proof.verified_at,
            "resolution_notes": payload.resolution_notes,
        },
    )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="trip.delivery_dispute_resolved",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_trip_values,
        new_values={"billing_status": trip.billing_status, "billable_at": trip.billable_at},
    )
    await resolve_active_exceptions(
        db,
        tenant_id,
        entity_type="delivery_proof",
        entity_id=proof.id,
        exception_type="delivery_proof_disputed",
        resolution_notes=payload.resolution_notes,
        actor_id=user_id,
    )
    await db.commit()
    await db.refresh(proof)
    await db.refresh(trip)
    return {
        "id": proof.id,
        "trip_id": proof.trip_id,
        "status": proof.status,
        "validation_method": proof.validation_method,
        "trip_billing_status": trip.billing_status,
        "billable_at": trip.billable_at,
    }


async def patch_delivery_proof(
    db: AsyncSession,
    tenant_id: UUID,
    proof_id: UUID,
    update_data: dict,
) -> dict:
    proof = await db.get(DeliveryProof, proof_id)
    if not proof:
        raise ApiError("delivery_proof_not_found", "Delivery proof not found.", status_code=404)
    # Verify tenant isolation via parent trip
    await _require_trip(db, tenant_id, proof.trip_id)
    patchable = {"notes", "receiver_name", "receiver_contact"}
    for field, value in update_data.items():
        if field in patchable and value is not None:
            setattr(proof, field, value)
    await db.commit()
    await db.refresh(proof)
    return {
        "id": proof.id,
        "trip_id": proof.trip_id,
        "receiver_name": proof.receiver_name,
        "receiver_contact": proof.receiver_contact,
        "notes": proof.notes,
        "status": proof.status,
    }
