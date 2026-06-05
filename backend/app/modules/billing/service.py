from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.billing.exporters import render_billing_export
from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.billing.schemas import BillingDocumentCreate, IssueBillingDocumentRequest
from app.modules.cargo.models import CargoManifest, DeliveryProof, LoadPermit, TransportDocument
from app.modules.contracts.models import Contract
from app.modules.files.models import File
from app.modules.files.service import save_generated_file
from app.modules.operations.models import OperationalWaiver
from app.modules.operations.service import has_active_waiver
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

NEGATIVE_MARGIN_APPROVAL_WAIVER = "negative_margin_approved"


async def create_billing_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    trip_id: UUID,
    reason: str,
) -> dict:
    """Create a billing waiver with status=pending_approval for a negative-margin trip."""
    trip = await db.scalar(select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id))
    if not trip:
        raise ApiError("trip_not_found", "Trip not found", status_code=404)

    existing = await db.scalar(
        select(OperationalWaiver).where(
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.entity_id == trip_id,
            OperationalWaiver.waiver_type == NEGATIVE_MARGIN_APPROVAL_WAIVER,
            OperationalWaiver.status == "pending_approval",
        )
    )
    if existing:
        raise ApiError(
            "waiver_already_pending",
            "A waiver is already pending approval for this trip.",
            status_code=409,
        )

    waiver = OperationalWaiver(
        tenant_id=tenant_id,
        entity_type="trip",
        entity_id=trip_id,
        waiver_type=NEGATIVE_MARGIN_APPROVAL_WAIVER,
        reason=reason,
        status="pending_approval",
        risk_level="medium",
    )
    db.add(waiver)
    await db.commit()
    await db.refresh(waiver)
    return {
        "id": waiver.id,
        "trip_id": trip_id,
        "status": waiver.status,
        "reason": waiver.reason,
        "approved_by": waiver.approved_by,
        "created_at": waiver.created_at,
    }


async def approve_billing_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    waiver_id: UUID,
    approver_id: UUID,
) -> dict:
    """Set waiver status=active. Trip can now enter billing cycle."""
    waiver = await db.scalar(
        select(OperationalWaiver).where(
            OperationalWaiver.id == waiver_id,
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.waiver_type == NEGATIVE_MARGIN_APPROVAL_WAIVER,
        )
    )
    if not waiver:
        raise ApiError("waiver_not_found", "Waiver not found", status_code=404)
    if waiver.status != "pending_approval":
        raise ApiError(
            "waiver_not_pending",
            f"Waiver is in status '{waiver.status}' — can only approve pending waivers.",
            status_code=409,
        )
    waiver.status = "active"
    waiver.approved_by = approver_id
    waiver.approved_at = datetime.now(UTC)
    await db.commit()
    return {"id": waiver.id, "status": "active", "approved_by": approver_id}


async def reject_billing_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    waiver_id: UUID,
    rejector_id: UUID,
) -> dict:
    """Set waiver status=rejected. Trip remains blocked from billing."""
    waiver = await db.scalar(
        select(OperationalWaiver).where(
            OperationalWaiver.id == waiver_id,
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.waiver_type == NEGATIVE_MARGIN_APPROVAL_WAIVER,
        )
    )
    if not waiver:
        raise ApiError("waiver_not_found", "Waiver not found", status_code=404)
    if waiver.status != "pending_approval":
        raise ApiError(
            "waiver_not_pending",
            f"Waiver is in status '{waiver.status}' — can only reject pending waivers.",
            status_code=409,
        )
    waiver.status = "rejected"
    waiver.approved_by = rejector_id
    await db.commit()
    return {"id": waiver.id, "status": "rejected"}


def serialize_billable_trip(
    trip: Trip,
    proof: DeliveryProof | None,
    contract: Contract | None,
    vehicle: Vehicle | None = None,
    waiver: OperationalWaiver | None = None,
) -> dict:
    if not proof:
        candidate_status = "pending_delivery_proof"
    elif proof.status == "disputed" or trip.billing_status == "delivery_disputed":
        candidate_status = "delivery_disputed"
    elif proof.status not in {"validated", "verified"}:
        candidate_status = "pending_delivery_validation"
    elif not contract:
        candidate_status = "uncontracted"
    elif trip.billing_status in {"billing_draft", "billed"}:
        candidate_status = trip.billing_status
    else:
        candidate_status = "billable"

    return {
        "trip_id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "vehicle_plate": vehicle.plate if vehicle else None,
        "contract_id": trip.contract_id,
        "contract_reference": trip.contract_reference,
        "client_name": contract.client_name if contract else None,
        "origin": trip.origin,
        "destination": trip.destination,
        "cargo_type": trip.cargo_type,
        "cargo_class": trip.cargo_class,
        "load_state": trip.load_state,
        "delivered_at": proof.delivered_at if proof else trip.actual_arrival,
        "delivery_proof_id": proof.id if proof else None,
        "delivery_proof_status": proof.status if proof else None,
        "billing_status": trip.billing_status,
        "candidate_status": candidate_status,
        "amount": contract.default_unit_price if contract else None,
        "waiver_status": waiver.status if waiver else None,
    }


def serialize_billing_item(item: BillingItem) -> dict:
    return {
        "id": item.id,
        "contract_id": item.contract_id,
        "billing_document_id": item.billing_document_id,
        "trip_id": item.trip_id,
        "load_permit_id": item.load_permit_id,
        "cargo_manifest_id": item.cargo_manifest_id,
        "transport_document_id": item.transport_document_id,
        "delivery_proof_id": item.delivery_proof_id,
        "client_reference": item.client_reference,
        "origin": item.origin,
        "destination": item.destination,
        "district": item.district,
        "cargo_description": item.cargo_description,
        "cargo_class": item.cargo_class,
        "load_state": item.load_state,
        "loaded_at": item.loaded_at,
        "delivered_at": item.delivered_at,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "amount": item.amount,
        "status": item.status,
        "created_at": item.created_at,
    }


def serialize_billing_document(document: BillingDocument, items: list[BillingItem]) -> dict:
    return {
        "id": document.id,
        "tenant_id": document.tenant_id,
        "contract_id": document.contract_id,
        "client_name": document.client_name,
        "contract_reference": document.contract_reference,
        "billing_period_start": document.billing_period_start,
        "billing_period_end": document.billing_period_end,
        "currency": document.currency,
        "subtotal": document.subtotal,
        "tax_amount": document.tax_amount,
        "total_amount": document.total_amount,
        "status": document.status,
        "issued_at": document.issued_at,
        "paid_at": document.paid_at,
        "file_id": document.file_id,
        "items": [serialize_billing_item(item) for item in items],
    }


def serialize_billing_document_summary(
    document: BillingDocument,
    item_count: int,
) -> dict:
    return {
        "id": document.id,
        "tenant_id": document.tenant_id,
        "contract_id": document.contract_id,
        "client_name": document.client_name,
        "contract_reference": document.contract_reference,
        "billing_period_start": document.billing_period_start,
        "billing_period_end": document.billing_period_end,
        "currency": document.currency,
        "subtotal": document.subtotal,
        "tax_amount": document.tax_amount,
        "total_amount": document.total_amount,
        "status": document.status,
        "issued_at": document.issued_at,
        "paid_at": document.paid_at,
        "file_id": document.file_id,
        "item_count": item_count,
        "created_at": document.created_at,
    }


async def require_margin_governance(
    db: AsyncSession,
    tenant_id: UUID,
    trip: Trip,
) -> None:
    margin = float(trip.actual_margin or 0)
    if trip.costs_reconciled_at is None or margin >= 0:
        return

    if await has_active_waiver(
        db,
        tenant_id,
        entity_type="trip",
        entity_id=trip.id,
        waiver_type=NEGATIVE_MARGIN_APPROVAL_WAIVER,
    ):
        return

    raise ApiError(
        "negative_margin_requires_approval",
        "Trip has negative margin and requires approval before billing.",
        status_code=status.HTTP_409_CONFLICT,
        details={
            "trip_id": str(trip.id),
            "actual_margin": margin,
            "required_waiver_type": NEGATIVE_MARGIN_APPROVAL_WAIVER,
        },
    )


async def list_billable_trips(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    client_name: str | None = None,
    contract_reference: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = (
        select(Trip, DeliveryProof, Contract, Vehicle)
        .join(DeliveryProof, DeliveryProof.trip_id == Trip.id, isouter=True)
        .join(Contract, Contract.id == Trip.contract_id, isouter=True)
        .join(Vehicle, Vehicle.id == Trip.vehicle_id, isouter=True)
        .where(Trip.tenant_id == tenant_id)
        .where(Trip.status.in_(("delivered", "closed")))
    )

    if client_name:
        query = query.where(Contract.client_name.ilike(f"%{client_name}%"))
    if contract_reference:
        query = query.where(Trip.contract_reference == contract_reference)
    if status_filter:
        query = query.where(Trip.billing_status == status_filter)
    if period_start:
        query = query.where(DeliveryProof.delivered_at >= period_start)
    if period_end:
        query = query.where(DeliveryProof.delivered_at < period_end)

    rows = await db.execute(query.order_by(Trip.actual_arrival.desc()).limit(limit).offset(offset))
    results = []
    for trip, proof, contract, vehicle in rows:
        waiver = await db.scalar(
            select(OperationalWaiver)
            .where(
                OperationalWaiver.tenant_id == tenant_id,
                OperationalWaiver.entity_type == "trip",
                OperationalWaiver.entity_id == trip.id,
                OperationalWaiver.waiver_type == NEGATIVE_MARGIN_APPROVAL_WAIVER,
            )
            .order_by(OperationalWaiver.created_at.desc())
        )
        results.append(serialize_billable_trip(trip, proof, contract, vehicle, waiver))
    return results


async def list_documents(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    item_count = func.count(BillingItem.id)
    query = (
        select(BillingDocument, item_count)
        .join(BillingItem, BillingItem.billing_document_id == BillingDocument.id, isouter=True)
        .where(BillingDocument.tenant_id == tenant_id)
        .group_by(BillingDocument.id)
    )
    if status_filter:
        query = query.where(BillingDocument.status == status_filter)
    if period_start:
        query = query.where(BillingDocument.billing_period_start >= period_start)
    if period_end:
        query = query.where(BillingDocument.billing_period_start < period_end)

    rows = await db.execute(
        query.order_by(BillingDocument.created_at.desc()).limit(limit).offset(offset)
    )
    return [
        serialize_billing_document_summary(document, int(count or 0))
        for document, count in rows
    ]


async def create_document(db: AsyncSession, tenant_id: UUID, payload: BillingDocumentCreate):
    if not payload.contract_id:
        raise ApiError(
            "contract_required",
            "Billing document requires a contract.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    contract = await db.get(Contract, payload.contract_id)
    if not contract or contract.tenant_id != tenant_id:
        raise ApiError("contract_not_found", "Contract not found.", status_code=404)

    document = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        contract_reference=contract.contract_reference,
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        currency=payload.currency,
        status="draft",
    )
    db.add(document)
    await db.flush()

    total = 0
    items: list[BillingItem] = []
    for trip_id in payload.trip_ids:
        trip = await db.get(Trip, trip_id)
        if not trip or trip.tenant_id != tenant_id:
            raise ApiError("trip_not_found", "Trip not found.", status_code=404)
        if trip.contract_id != contract.id:
            raise ApiError(
                "trip_contract_mismatch",
                "Trip is not linked to this contract.",
                status_code=409,
            )
        if trip.billing_status != "billable":
            raise ApiError(
                "trip_not_billable",
                "Trip is not ready for billing.",
                status_code=409,
                details={"trip_id": str(trip.id), "billing_status": trip.billing_status},
            )
        await require_margin_governance(db, tenant_id, trip)

        proof = await db.scalar(
            select(DeliveryProof)
            .where(
                DeliveryProof.tenant_id == tenant_id,
                DeliveryProof.trip_id == trip.id,
                DeliveryProof.status.in_(("validated", "verified")),
            )
            .order_by(DeliveryProof.delivered_at.desc())
        )
        if not proof:
            raise ApiError(
                "delivery_proof_required",
                "Validated delivery proof is required.",
                status_code=409,
            )
        if not (payload.billing_period_start <= proof.delivered_at < payload.billing_period_end):
            raise ApiError(
                "trip_outside_billing_period",
                "Trip delivery date is outside billing period.",
                status_code=409,
                details={"trip_id": str(trip.id), "delivered_at": proof.delivered_at.isoformat()},
            )

        load_permit = await db.scalar(
            select(LoadPermit)
            .where(LoadPermit.tenant_id == tenant_id, LoadPermit.trip_id == trip.id)
            .order_by(LoadPermit.created_at.desc())
        )
        manifest = await db.scalar(
            select(CargoManifest)
            .where(CargoManifest.tenant_id == tenant_id, CargoManifest.trip_id == trip.id)
            .order_by(CargoManifest.created_at.desc())
        )
        transport_document = await db.scalar(
            select(TransportDocument)
            .where(TransportDocument.tenant_id == tenant_id, TransportDocument.trip_id == trip.id)
            .order_by(TransportDocument.created_at.desc())
        )

        amount = contract.default_unit_price or 0
        item = BillingItem(
            tenant_id=tenant_id,
            contract_id=contract.id,
            billing_document_id=document.id,
            trip_id=trip.id,
            load_permit_id=load_permit.id if load_permit else None,
            cargo_manifest_id=manifest.id if manifest else None,
            transport_document_id=transport_document.id if transport_document else None,
            delivery_proof_id=proof.id,
            client_reference=trip.contract_reference,
            origin=trip.origin,
            destination=trip.destination,
            district=load_permit.district if load_permit else None,
            cargo_description=trip.cargo_type,
            cargo_class=trip.cargo_class,
            load_state=trip.load_state,
            loaded_at=trip.actual_departure,
            delivered_at=proof.delivered_at,
            quantity=proof.quantity_delivered,
            unit_price=contract.default_unit_price,
            amount=amount,
            status="draft",
        )
        db.add(item)
        items.append(item)
        total += amount

        trip.billing_status = "billing_draft"
        trip.billing_document_id = document.id

    document.subtotal = total
    document.total_amount = total
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="billing.document_created",
        entity_type="billing_document",
        entity_id=document.id,
        new_values={
            "contract_id": document.contract_id,
            "contract_reference": document.contract_reference,
            "billing_period_start": document.billing_period_start,
            "billing_period_end": document.billing_period_end,
            "currency": document.currency,
            "subtotal": document.subtotal,
            "total_amount": document.total_amount,
            "status": document.status,
            "trip_ids": [trip_id for trip_id in payload.trip_ids],
            "item_count": len(items),
        },
    )
    for item in items:
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            action="billing.item_created",
            entity_type="billing_item",
            entity_id=item.id,
            new_values={
                "billing_document_id": document.id,
                "contract_id": item.contract_id,
                "trip_id": item.trip_id,
                "delivery_proof_id": item.delivery_proof_id,
                "amount": item.amount,
                "status": item.status,
            },
        )
    await db.commit()
    await db.refresh(document)
    return serialize_billing_document(document, items)


async def get_document(db: AsyncSession, tenant_id: UUID, document_id: UUID) -> dict:
    document = await db.get(BillingDocument, document_id)
    if not document or document.tenant_id != tenant_id:
        raise ApiError(
            "billing_document_not_found",
            "Billing document not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    result = await db.execute(
        select(BillingItem)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.billing_document_id == document.id,
        )
        .order_by(BillingItem.delivered_at.asc())
    )
    return serialize_billing_document(document, list(result.scalars()))


async def issue_document(
    db: AsyncSession,
    tenant_id: UUID,
    document_id: UUID,
    payload: IssueBillingDocumentRequest,
) -> dict:
    document = await db.get(BillingDocument, document_id)
    if not document or document.tenant_id != tenant_id:
        raise ApiError(
            "billing_document_not_found",
            "Billing document not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if document.status == "issued":
        return await get_document(db, tenant_id, document_id)
    if document.status != "draft":
        raise ApiError(
            "invalid_billing_document_status",
            "Only draft billing documents can be issued.",
            status_code=status.HTTP_409_CONFLICT,
            details={"status": document.status},
        )

    result = await db.execute(
        select(BillingItem).where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.billing_document_id == document.id,
        )
    )
    items = list(result.scalars())
    if not items:
        raise ApiError(
            "empty_billing_document",
            "Billing document has no items.",
            status_code=status.HTTP_409_CONFLICT,
        )

    issued_at = payload.issued_at or datetime.now(UTC)
    old_document_values = {"status": document.status, "issued_at": document.issued_at}
    trip_old_values: dict[UUID, dict] = {}
    document.status = "issued"
    document.issued_at = issued_at

    for item in items:
        item.status = "billed"
        trip = await db.get(Trip, item.trip_id)
        if trip and trip.tenant_id == tenant_id:
            trip_old_values[trip.id] = {
                "billing_status": trip.billing_status,
                "billed_at": trip.billed_at,
                "billing_document_id": trip.billing_document_id,
            }
            trip.billing_status = "billed"
            trip.billed_at = issued_at
            trip.billing_document_id = document.id

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="billing.document_issued",
        entity_type="billing_document",
        entity_id=document.id,
        old_values=old_document_values,
        new_values={
            "status": document.status,
            "issued_at": document.issued_at,
            "item_count": len(items),
        },
    )
    for item in items:
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            action="billing.item_billed",
            entity_type="billing_item",
            entity_id=item.id,
            new_values={
                "billing_document_id": document.id,
                "trip_id": item.trip_id,
                "status": item.status,
            },
        )
        if item.trip_id in trip_old_values:
            await record_audit_log(
                db,
                tenant_id=tenant_id,
                action="trip.billing_finalized",
                entity_type="trip",
                entity_id=item.trip_id,
                old_values=trip_old_values[item.trip_id],
                new_values={
                    "billing_status": "billed",
                    "billed_at": issued_at,
                    "billing_document_id": document.id,
                },
            )
    await db.commit()
    await db.refresh(document)
    refreshed_items = await db.execute(
        select(BillingItem)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.billing_document_id == document.id,
        )
        .order_by(BillingItem.delivered_at.asc())
    )
    return serialize_billing_document(document, list(refreshed_items.scalars()))


async def export_document(
    db: AsyncSession,
    tenant_id: UUID,
    document_id: UUID,
    export_format: str = "pdf",
) -> dict:
    document = await db.get(BillingDocument, document_id)
    if not document or document.tenant_id != tenant_id:
        raise ApiError(
            "billing_document_not_found",
            "Billing document not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if document.status != "issued":
        raise ApiError(
            "billing_document_not_issued",
            "Only issued billing documents can be exported.",
            status_code=status.HTTP_409_CONFLICT,
            details={"status": document.status},
        )
    if export_format not in {"pdf", "xlsx"}:
        raise ApiError(
            "unsupported_export_format",
            "Supported export formats are pdf and xlsx.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"format": export_format},
        )
    existing_file = await db.scalar(
        select(File)
        .where(
            File.tenant_id == tenant_id,
            File.entity_type == "billing_document",
            File.entity_id == document.id,
            File.file_type == export_format,
        )
        .order_by(File.uploaded_at.desc())
    )
    if existing_file:
        return _serialize_export(document, existing_file, export_format)

    result = await db.execute(
        select(BillingItem)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.billing_document_id == document.id,
        )
        .order_by(BillingItem.delivered_at.asc())
    )
    items = list(result.scalars())
    artifact = render_billing_export(document, items, export_format)
    stored_file = await save_generated_file(
        db,
        tenant_id,
        content=artifact.content,
        filename=artifact.filename,
        mime_type=artifact.content_type,
        file_type=export_format,
        entity_type="billing_document",
        entity_id=document.id,
    )
    document.file_id = stored_file.id
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="billing.document_exported",
        entity_type="billing_document",
        entity_id=document.id,
        new_values={
            "export_format": export_format,
            "file_id": stored_file.id,
            "filename": stored_file.original_name,
            "size_bytes": stored_file.size_bytes,
            "sha256_hash": stored_file.sha256_hash,
        },
    )
    await db.commit()

    return _serialize_export(document, stored_file, export_format)


def _serialize_export(document: BillingDocument, stored_file: File, export_format: str) -> dict:
    return {
        "billing_document_id": document.id,
        "export_format": export_format,
        "file_id": stored_file.id,
        "filename": stored_file.original_name,
        "content_type": stored_file.mime_type,
        "size_bytes": stored_file.size_bytes,
        "sha256_hash": stored_file.sha256_hash,
        "status": "generated",
        "download_url": f"/api/v1/files/{stored_file.id}/download",
        "message": "Documento gerado com layout profissional ROTAS.",
    }
