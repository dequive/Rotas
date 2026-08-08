from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.billing.domain import resolve_iva
from app.modules.billing.exporters import render_billing_export
from app.modules.billing.models import (
    BillingDocument,
    BillingItem,
    ClientPayment,
    FiscalCounter,
    PaymentAllocation,
)
from app.modules.billing.schemas import BillingDocumentCreate, IssueBillingDocumentRequest
from app.modules.cargo.models import CargoManifest, DeliveryProof, LoadPermit, TransportDocument
from app.modules.cargo.service import BILLABLE_PROOF_STATUSES
from app.modules.contracts.models import Contract
from app.modules.files.models import File
from app.modules.files.service import save_generated_file
from app.modules.operations.models import OperationalWaiver
from app.modules.operations.service import has_active_waiver
from app.modules.tenants.models import Tenant, TenantDocumentProfile
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

NEGATIVE_MARGIN_APPROVAL_WAIVER = "negative_margin_approved"


async def _assign_invoice_number(
    db: AsyncSession,
    document: "BillingDocument",
    tenant_id: UUID,
) -> str:
    """Assign a gap-free sequential invoice number using a transactional row lock.

    Uses FiscalCounter with SELECT FOR UPDATE so that a rollback undoes the
    increment — no gaps in the fiscal sequence (FISC-01 AT Mozambique requirement).
    Idempotent: returns existing value if already set.
    """
    import uuid as _uuid

    if document.invoice_number:
        return document.invoice_number

    profile = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == tenant_id)
    )
    prefix = (profile.invoice_prefix or "").strip() if profile else ""
    padding = profile.invoice_seq_padding if profile else 4
    per_type = profile.per_type_sequences if profile else False

    fiscal_year = (
        document.billing_period_start.year
        if document.billing_period_start
        else datetime.now(UTC).year
    )
    doc_type = (document.document_type or "") if per_type else ""

    # Ensure counter row exists (race-safe: concurrent inserts → ON CONFLICT DO NOTHING)
    await db.execute(
        pg_insert(FiscalCounter)
        .values(
            id=_uuid.uuid4(),
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            doc_type=doc_type,
            last_number=0,
        )
        .on_conflict_do_nothing(constraint="uq_fiscal_counter_key")
    )
    await db.flush()  # row must exist before SELECT FOR UPDATE

    # Lock counter row — rollback undoes the increment, guaranteeing no gaps
    counter = await db.scalar(
        select(FiscalCounter)
        .where(
            FiscalCounter.tenant_id == tenant_id,
            FiscalCounter.fiscal_year == fiscal_year,
            FiscalCounter.doc_type == doc_type,
        )
        .with_for_update()
    )
    if counter is None:
        raise RuntimeError("Fiscal counter was not created")
    counter.last_number += 1
    seq_str = str(counter.last_number).zfill(padding)

    if prefix:
        invoice_number = f"{prefix} {fiscal_year}/{seq_str}"
    else:
        invoice_number = f"{fiscal_year}/{seq_str}"

    document.invoice_number = invoice_number
    return invoice_number


def _format_address(profile: "TenantDocumentProfile") -> str:
    parts = [p for p in [profile.address_line1, profile.address_line2] if p]
    if profile.city:
        city_part = profile.city
        if profile.country:
            city_part = f"{city_part} — {profile.country}"
        parts.append(city_part)
    return ", ".join(parts) if parts else ""


async def _snapshot_profile(
    db: AsyncSession,
    document: "BillingDocument",
    tenant_id: UUID,
) -> None:
    """Copy TenantDocumentProfile fields into BillingDocument snapshot columns at creation."""
    profile = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == tenant_id)
    )
    if not profile:
        return
    document.issuer_address = _format_address(profile) or None
    document.issuer_phone = profile.phone
    document.issuer_email = profile.email
    document.issuer_city = profile.city
    document.payment_conditions = profile.payment_conditions
    if profile.show_bank_details and profile.bank_name:
        legal = profile.legal_name or document.issuer_name or "—"
        document.issuer_bank_details = (
            f"Banco {profile.bank_name} | Titular: {legal} "
            f"| Conta: {profile.bank_account or '—'} | NIB: {profile.bank_nib or '—'}"
        )


async def create_billing_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID | None,
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
    approver_id: UUID | None,
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
    rejector_id: UUID | None,
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
        "iva_rate": item.iva_rate,
        "iva_amount": item.iva_amount,
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
        "due_date": document.due_date,
        "file_id": document.file_id,
        "invoice_number": document.invoice_number,
        "iva_rate": document.iva_rate,
        "document_type": document.document_type,
        "parent_document_id": document.parent_document_id,
        "client_nuit": document.client_nuit,
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
        "client_id": str(document.client_id) if document.client_id else None,
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
        "due_date": document.due_date,
        "file_id": document.file_id,
        "invoice_number": document.invoice_number,
        "document_type": document.document_type,
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
        .where(Trip.km_end.is_not(None))
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
    rows_list = list(rows)

    # Bulk-fetch all waivers for the result set in one query (eliminates N+1)
    trip_ids = [row[0].id for row in rows_list]
    waiver_map: dict = {}
    if trip_ids:
        waiver_rows = await db.execute(
            select(OperationalWaiver)
            .where(
                OperationalWaiver.tenant_id == tenant_id,
                OperationalWaiver.entity_type == "trip",
                OperationalWaiver.entity_id.in_(trip_ids),
                OperationalWaiver.waiver_type == NEGATIVE_MARGIN_APPROVAL_WAIVER,
            )
            .order_by(OperationalWaiver.created_at.desc())
        )
        for w in waiver_rows.scalars():
            # Keep first (most-recent) waiver per trip
            if w.entity_id not in waiver_map:
                waiver_map[w.entity_id] = w

    results = []
    for trip, proof, contract, vehicle in rows_list:
        waiver = waiver_map.get(trip.id)
        results.append(serialize_billable_trip(trip, proof, contract, vehicle, waiver))
    return results


async def list_documents(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    document_type: str | None = None,
    client_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List billing documents with optional filters. Returns {items, total}."""
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
    if document_type:
        query = query.where(BillingDocument.document_type == document_type)
    if client_id:
        query = query.where(BillingDocument.client_id == client_id)

    # COUNT query with same filters (without pagination)
    count_query = select(func.count(BillingDocument.id)).where(
        BillingDocument.tenant_id == tenant_id
    )
    if status_filter:
        count_query = count_query.where(BillingDocument.status == status_filter)
    if period_start:
        count_query = count_query.where(BillingDocument.billing_period_start >= period_start)
    if period_end:
        count_query = count_query.where(BillingDocument.billing_period_start < period_end)
    if document_type:
        count_query = count_query.where(BillingDocument.document_type == document_type)
    if client_id:
        count_query = count_query.where(BillingDocument.client_id == client_id)

    total = await db.scalar(count_query) or 0
    rows = await db.execute(
        query.order_by(BillingDocument.created_at.desc()).limit(limit).offset(offset)
    )
    return {
        "items": [
            serialize_billing_document_summary(document, int(count or 0))
            for document, count in rows
        ],
        "total": int(total),
    }


async def create_document(db: AsyncSession, tenant_id: UUID, payload: BillingDocumentCreate):
    if not payload.contract_id:
        raise ApiError(
            "contract_required",
            "Billing document requires a contract.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    contract = await db.get(Contract, payload.contract_id)
    if not contract or contract.tenant_id != tenant_id:
        raise ApiError("contract_not_found", "Contract not found.", status_code=404)

    tenant = await db.get(Tenant, tenant_id)
    issuer_name = tenant.name if tenant else "ROTAS"
    issuer_nuit = tenant.nuit if tenant else None

    document = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        contract_reference=contract.contract_reference,
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        currency=payload.currency,
        status="draft",
        client_nuit=payload.client_nuit,
        issuer_name=issuer_name,
        issuer_nuit=issuer_nuit,
    )
    db.add(document)
    await db.flush()
    await _snapshot_profile(db, document, tenant_id)

    total = Decimal("0")
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
                DeliveryProof.status.in_(BILLABLE_PROOF_STATUSES),
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

        from app.modules.vehicles.models import Vehicle

        vehicle = await db.get(Vehicle, trip.vehicle_id) if trip.vehicle_id else None
        vehicle_plate = vehicle.plate if vehicle else ""

        lp_str = (
            f" LP:{load_permit.permit_number}" if load_permit and load_permit.permit_number else ""
        )
        veh_str = f" [{vehicle_plate}]" if vehicle_plate else ""
        base_cargo = trip.cargo_type or "Serviço"
        enhanced_cargo_desc = f"{base_cargo}{veh_str}{lp_str}"

        amount = Decimal(str(contract.default_unit_price or 0))
        iva_rate, iva_basis = resolve_iva(trip, contract)
        iva_amount = (amount * iva_rate).quantize(Decimal("0.01"))
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
            cargo_description=enhanced_cargo_desc,
            cargo_class=trip.cargo_class,
            load_state=trip.load_state,
            loaded_at=trip.actual_departure,
            delivered_at=proof.delivered_at,
            quantity=proof.quantity_delivered,
            unit_price=contract.default_unit_price,
            amount=amount,
            iva_rate=iva_rate,
            iva_basis=iva_basis,
            iva_amount=iva_amount,
            status="draft",
        )
        db.add(item)
        items.append(item)
        total += amount

        trip.billing_status = "billing_draft"
        trip.billing_document_id = document.id

    document.subtotal = total
    document.total_amount = total
    # invoice_number intentionally not assigned here — assigned only in issue_document (FISC-01)
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

    if not document.client_nuit or not document.client_nuit.strip():
        raise ApiError(
            "client_nuit_required",
            "O NUIT do cliente é obrigatório para emitir um documento fiscal. "
            "Actualize o documento com client_nuit antes de emitir.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    issued_at = payload.issued_at or datetime.now(UTC)
    old_document_values = {"status": document.status, "issued_at": document.issued_at}

    # Compute due_date from contract.payment_terms_days (default 30 days)
    from datetime import timedelta

    contract = await db.get(Contract, document.contract_id) if document.contract_id else None
    payment_terms = (contract.payment_terms_days if contract else 30) or 30
    document.due_date = issued_at + timedelta(days=payment_terms)
    trip_old_values: dict[UUID, dict] = {}

    # FISC-01: Assign sequential invoice number from PostgreSQL SEQUENCE
    await _assign_invoice_number(db, document, tenant_id)

    # FISC-02: Recompute IVA totals from per-item iva_amount values
    document.subtotal = sum(
        (item.amount for item in items),
        Decimal("0"),
    ).quantize(Decimal("0.01"))
    document.tax_amount = sum(
        (item.iva_amount or Decimal("0") for item in items),
        Decimal("0"),
    ).quantize(Decimal("0.01"))
    document.total_amount = (document.subtotal + document.tax_amount).quantize(Decimal("0.01"))
    rates = {item.iva_rate for item in items if item.iva_rate is not None}
    document.iva_rate = rates.pop() if len(rates) == 1 else None

    # INVARIANT: verify subtotal + tax_amount == total_amount after recomputation
    if abs(document.subtotal + document.tax_amount - document.total_amount) > Decimal("0.01"):
        raise ApiError(
            "billing_total_inconsistency",
            f"subtotal ({document.subtotal}) + tax ({document.tax_amount}) "
            f"!= total ({document.total_amount})",
            status_code=422,
        )

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

    # --- HOOK CONTABILISTICO (Fase 7) ---
    from app.modules.accounting.models import Account
    from app.modules.accounting.schemas import JournalEntryCreate
    from app.modules.accounting.schemas import JournalItemCreate as AccJournalItemCreate
    from app.modules.accounting.services import create_journal_entry

    if document.total_amount and document.total_amount > 0:
        acct_clients = await db.scalar(
            select(Account)
            .where(Account.tenant_id == tenant_id, Account.code.like("411%"))
            .limit(1)
        )
        acct_sales = await db.scalar(
            select(Account)
            .where(Account.tenant_id == tenant_id, Account.code.like("711%"))
            .limit(1)
        )

        if acct_clients and acct_sales:
            await create_journal_entry(
                db,
                tenant_id=tenant_id,
                payload=JournalEntryCreate(
                    date=datetime.now(),
                    journal_type="VEN",
                    description=(
                        f"Fatura {document.invoice_number or str(document.id)[:8]} "
                        f"ao Cliente {document.client_name}"
                    ),
                    items=[
                        AccJournalItemCreate(
                            account_id=acct_clients.id,
                            description="Valor A Receber",
                            debit=document.total_amount,
                            credit=Decimal("0.00"),
                        ),
                        AccJournalItemCreate(
                            account_id=acct_sales.id,
                            description="Prestacao de Servicos de Transporte",
                            debit=Decimal("0.00"),
                            credit=document.total_amount,
                        ),
                    ],
                ),
                actor_id=None,
            )
    # ------------------------------------

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
            "invoice_number": document.invoice_number,
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
        trip_id = item.trip_id
        if trip_id is not None and trip_id in trip_old_values:
            await record_audit_log(
                db,
                tenant_id=tenant_id,
                action="trip.billing_finalized",
                entity_type="trip",
                entity_id=trip_id,
                old_values=trip_old_values[trip_id],
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


async def enqueue_export_job(
    db: AsyncSession,
    tenant_id: UUID,
    document_id: UUID,
    export_format: str,
    arq_redis: ArqRedis,
) -> dict:
    """Enqueue an ARQ export job and create ExportJob record.

    Idempotent: returns existing queued/processing job if one exists for the same document
    and format, rather than creating a duplicate.
    """
    from app.modules.billing.models import ExportJob

    existing = await db.scalar(
        select(ExportJob).where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.entity_id == document_id,
            ExportJob.job_type == f"billing_{export_format}",
            ExportJob.status.in_(["queued", "processing"]),
        )
    )
    if existing:
        return {"job_id": str(existing.id), "status": existing.status}

    job_record = ExportJob(
        tenant_id=tenant_id,
        job_type=f"billing_{export_format}",
        entity_id=document_id,
        status="queued",
    )
    db.add(job_record)
    await db.commit()
    await db.refresh(job_record)

    await arq_redis.enqueue_job(
        "generate_billing_export",
        job_id=str(job_record.id),
        document_id=str(document_id),
        export_format=export_format,
        tenant_id=str(tenant_id),
    )
    return {"job_id": str(job_record.id), "status": "queued"}


async def create_compliance_report_job(
    db: AsyncSession,
    tenant_id: UUID,
    month: str,
    arq: "ArqRedis",
) -> dict:
    """Create an ExportJob and enqueue the ARQ task for monthly compliance XLSX (FISC-03).

    Args:
        month: YYYY-MM format string, e.g. "2026-01"
    Returns:
        dict with job_id and status
    """
    from app.modules.billing.models import ExportJob

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ApiError(
            "invalid_month_format",
            "month must be in YYYY-MM format (e.g. 2026-01)",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc

    existing = await db.scalar(
        select(ExportJob).where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.job_type == "compliance_report",
            ExportJob.status.in_(["queued", "processing"]),
        )
    )
    if existing:
        return {"job_id": str(existing.id), "status": existing.status}

    job = ExportJob(
        tenant_id=tenant_id,
        job_type="compliance_report",
        entity_id=None,
        status="queued",
    )
    db.add(job)
    await db.flush()

    await arq.enqueue_job(
        "task_export_compliance_report",
        str(job.id),
        month,
        str(tenant_id),
    )

    await db.commit()
    return {"job_id": str(job.id), "status": job.status}


async def get_export_job_status(db: AsyncSession, tenant_id: UUID, job_id: UUID) -> dict:
    """Return current status of an export job. Tenant-isolated."""
    from app.modules.billing.models import ExportJob

    job = await db.scalar(
        select(ExportJob).where(ExportJob.id == job_id, ExportJob.tenant_id == tenant_id)
    )
    if not job:
        raise ApiError("job_not_found", "Export job not found", status_code=404)
    return {"job_id": str(job.id), "status": job.status, "job_type": job.job_type}


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


# ── SM-01: BillingDocument State Machine ─────────────────────────────────────

_BILLING_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"issued", "cancelled"},
    "issued": {"paid", "overdue"},  # "cancelled" removed — issued docs cannot be cancelled (FISC)
    "overdue": {"paid", "cancelled"},
    "paid": set(),  # terminal
    "cancelled": set(),  # terminal
}


async def transition_billing_document(
    db: AsyncSession,
    *,
    document: BillingDocument,
    new_status: str,
    user_id: UUID | None,
    tenant_id: UUID,
    paid_at: datetime | None = None,
    cancellation_reason: str | None = None,
) -> BillingDocument:
    """Guard-enforced state transition for BillingDocument (SM-01).

    Raises ApiError(409) for invalid transitions.
    All transitions are recorded in audit_log within the same transaction.
    """
    allowed = _BILLING_VALID_TRANSITIONS.get(document.status, set())
    if new_status not in allowed:
        raise ApiError(
            "invalid_state_transition",
            f"BillingDocument cannot transition from '{document.status}' to '{new_status}'",
            status_code=409,
        )
    if new_status == "cancelled" and not cancellation_reason:
        raise ApiError(
            "cancellation_reason_required",
            "cancellation_reason is required when cancelling a billing document",
            status_code=422,
        )

    old_status = document.status
    document.status = new_status

    if new_status == "paid":
        document.paid_at = paid_at or datetime.now(UTC)
    elif new_status == "overdue":
        document.overdue_since_at = datetime.now(UTC)
    elif new_status == "cancelled":
        document.cancellation_reason = cancellation_reason

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action=f"billing.document.{new_status}",
        entity_type="billing_document",
        entity_id=document.id,
        user_id=user_id,
        old_values={"status": old_status},
        new_values={
            "status": new_status,
            "paid_at": document.paid_at.isoformat() if document.paid_at else None,
        },
    )
    db.add(document)
    return document


async def mark_billing_document_paid(
    db: AsyncSession,
    *,
    document_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    paid_at: datetime | None = None,
) -> BillingDocument:
    """SM-01: Transition BillingDocument to 'paid'. Allowed from 'issued' or 'overdue'."""
    doc = await db.get(BillingDocument, document_id)
    if not doc or doc.tenant_id != tenant_id:
        raise ApiError("not_found", "BillingDocument not found", status_code=404)
    return await transition_billing_document(
        db,
        document=doc,
        new_status="paid",
        user_id=user_id,
        tenant_id=tenant_id,
        paid_at=paid_at,
    )


async def cancel_billing_document(
    db: AsyncSession,
    *,
    document_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    reason: str,
) -> BillingDocument:
    """SM-01: Transition BillingDocument to 'cancelled'. Requires reason.

    Allowed from 'draft' or 'overdue'.
    """
    doc = await db.get(BillingDocument, document_id)
    if not doc or doc.tenant_id != tenant_id:
        raise ApiError("not_found", "BillingDocument not found", status_code=404)
    return await transition_billing_document(
        db,
        document=doc,
        new_status="cancelled",
        user_id=user_id,
        tenant_id=tenant_id,
        cancellation_reason=reason,
    )


# ── FDOC-02: Nota de Débito ───────────────────────────────────────────────────


async def create_debit_note(
    db: AsyncSession,
    tenant_id: UUID,
    parent_id: UUID,
    amount: Decimal,
    reason: str,
    iva_rate: Decimal | None = None,
) -> dict:
    """Create a Nota de Débito child document referencing an issued/paid invoice.

    The debit note receives a sequential invoice_number from the same FISC-01 sequence.
    Parent status is not modified. amount must be positive (the additional charge).
    iva_rate defaults to the domestic standard rate via resolve_iva (trip=None).
    """
    parent = await db.get(BillingDocument, parent_id)
    if not parent or parent.tenant_id != tenant_id:
        raise ApiError("parent_not_found", "Parent billing document not found", status_code=404)
    if parent.status not in ("issued", "paid"):
        raise ApiError(
            "parent_not_issued",
            f"Debit notes can only be created against issued or paid documents"
            f" (parent status: {parent.status})",
            status_code=409,
        )

    _resolved_rate, _resolved_basis = resolve_iva(trip=None, contract=None)
    effective_rate = iva_rate if iva_rate is not None else _resolved_rate
    effective_basis = "contract_override" if iva_rate is not None else _resolved_basis
    iva_amount = (amount * effective_rate).quantize(Decimal("0.01"))
    total = amount + iva_amount

    note = BillingDocument(
        tenant_id=tenant_id,
        contract_id=parent.contract_id,
        client_id=getattr(parent, "client_id", None),
        client_name=parent.client_name,
        client_nuit=parent.client_nuit,
        contract_reference=parent.contract_reference,
        billing_period_start=parent.billing_period_start,
        billing_period_end=parent.billing_period_end,
        currency=parent.currency,
        subtotal=amount,
        tax_amount=iva_amount,
        total_amount=total,
        iva_rate=effective_rate,
        iva_basis=effective_basis,
        document_type="debit_note",
        parent_document_id=parent_id,
        parent_invoice_number=parent.invoice_number,
        issuer_name=parent.issuer_name,
        issuer_nuit=parent.issuer_nuit,
        status="issued",
        issued_at=datetime.now(UTC),
    )
    db.add(note)
    await db.flush()
    await _snapshot_profile(db, note, tenant_id)
    await _assign_invoice_number(db, note, tenant_id)
    await db.commit()
    await db.refresh(note)

    await record_audit_log(
        db=db,
        tenant_id=tenant_id,
        action="billing.debit_note_created",
        entity_type="billing_document",
        entity_id=note.id,
        new_values={
            "invoice_number": note.invoice_number,
            "parent_id": str(parent_id),
            "amount": str(amount),
            "reason": reason,
        },
    )

    return {
        "id": note.id,
        "invoice_number": note.invoice_number,
        "document_type": note.document_type,
        "parent_document_id": note.parent_document_id,
        "parent_invoice_number": parent.invoice_number,
        "subtotal": note.subtotal,
        "tax_amount": note.tax_amount,
        "total_amount": note.total_amount,
        "status": note.status,
        "issued_at": note.issued_at,
    }


# ── FDOC-03: Nota de Crédito ──────────────────────────────────────────────────


async def create_credit_note(
    db: AsyncSession,
    tenant_id: UUID,
    parent_id: UUID,
    amount: Decimal,
    reason: str,
    iva_rate: Decimal | None = None,
) -> dict:
    """Create a Nota de Crédito child document referencing an issued/paid invoice.

    The credit note receives a sequential invoice_number from the same FISC-01 sequence.
    amount is the credit amount (positive value — type signals direction).
    Parent status is not modified.
    iva_rate defaults to the domestic standard rate via resolve_iva (trip=None).
    """
    parent = await db.get(BillingDocument, parent_id)
    if not parent or parent.tenant_id != tenant_id:
        raise ApiError("parent_not_found", "Parent billing document not found", status_code=404)
    if parent.status not in ("issued", "paid"):
        raise ApiError(
            "parent_not_issued",
            f"Credit notes can only be created against issued or paid documents"
            f" (parent status: {parent.status})",
            status_code=409,
        )

    _resolved_rate, _resolved_basis = resolve_iva(trip=None, contract=None)
    effective_rate = iva_rate if iva_rate is not None else _resolved_rate
    effective_basis = "contract_override" if iva_rate is not None else _resolved_basis
    iva_amount = (amount * effective_rate).quantize(Decimal("0.01"))
    total = amount + iva_amount

    note = BillingDocument(
        tenant_id=tenant_id,
        contract_id=parent.contract_id,
        client_id=getattr(parent, "client_id", None),
        client_name=parent.client_name,
        client_nuit=parent.client_nuit,
        contract_reference=parent.contract_reference,
        billing_period_start=parent.billing_period_start,
        billing_period_end=parent.billing_period_end,
        currency=parent.currency,
        subtotal=amount,
        tax_amount=iva_amount,
        total_amount=total,
        iva_rate=effective_rate,
        iva_basis=effective_basis,
        document_type="credit_note",
        parent_document_id=parent_id,
        parent_invoice_number=parent.invoice_number,
        issuer_name=parent.issuer_name,
        issuer_nuit=parent.issuer_nuit,
        status="issued",
        issued_at=datetime.now(UTC),
    )
    db.add(note)
    await db.flush()
    await _snapshot_profile(db, note, tenant_id)
    await _assign_invoice_number(db, note, tenant_id)
    await db.commit()
    await db.refresh(note)

    await record_audit_log(
        db=db,
        tenant_id=tenant_id,
        action="billing.credit_note_created",
        entity_type="billing_document",
        entity_id=note.id,
        new_values={
            "invoice_number": note.invoice_number,
            "parent_id": str(parent_id),
            "amount": str(amount),
            "reason": reason,
        },
    )

    return {
        "id": note.id,
        "invoice_number": note.invoice_number,
        "document_type": note.document_type,
        "parent_document_id": note.parent_document_id,
        "parent_invoice_number": parent.invoice_number,
        "subtotal": note.subtotal,
        "tax_amount": note.tax_amount,
        "total_amount": note.total_amount,
        "status": note.status,
        "issued_at": note.issued_at,
    }


# ── FDOC-04: Fatura-Recibo + Recibo ──────────────────────────────────────────


async def create_invoice_receipt(
    db: AsyncSession,
    tenant_id: UUID,
    parent_id: UUID,
) -> dict:
    """Transition parent invoice to paid and create a Fatura-Recibo child document.

    The Fatura-Recibo is emitted simultaneously with full payment — it serves as both
    invoice and receipt in one document (common in Mozambican SME practice).
    """
    parent = await db.get(BillingDocument, parent_id)
    if not parent or parent.tenant_id != tenant_id:
        raise ApiError("parent_not_found", "Parent billing document not found", status_code=404)
    if parent.status not in ("issued", "overdue"):
        raise ApiError(
            "parent_not_issued",
            f"Invoice-receipt can only be created against issued documents"
            f" (parent status: {parent.status})",
            status_code=409,
        )

    now = datetime.now(UTC)

    note = BillingDocument(
        tenant_id=tenant_id,
        contract_id=parent.contract_id,
        client_id=getattr(parent, "client_id", None),
        client_name=parent.client_name,
        client_nuit=parent.client_nuit,
        contract_reference=parent.contract_reference,
        billing_period_start=parent.billing_period_start,
        billing_period_end=parent.billing_period_end,
        currency=parent.currency,
        subtotal=parent.subtotal,
        tax_amount=parent.tax_amount,
        total_amount=parent.total_amount,
        iva_rate=parent.iva_rate,
        document_type="invoice_receipt",
        parent_document_id=parent_id,
        parent_invoice_number=parent.invoice_number,
        issuer_name=parent.issuer_name,
        issuer_nuit=parent.issuer_nuit,
        status="issued",
        issued_at=now,
    )
    db.add(note)
    await db.flush()
    await _snapshot_profile(db, note, tenant_id)
    await _assign_invoice_number(db, note, tenant_id)

    parent.status = "paid"
    parent.paid_at = now

    await record_audit_log(
        db=db,
        tenant_id=tenant_id,
        action="billing.invoice_receipt_created",
        entity_type="billing_document",
        entity_id=note.id,
        new_values={
            "invoice_number": note.invoice_number,
            "parent_id": str(parent_id),
            "parent_invoice_number": parent.invoice_number,
            "total_amount": str(note.total_amount),
            "document_type": "invoice_receipt",
        },
    )

    await db.commit()
    await db.refresh(note)
    await db.refresh(parent)

    return {
        "id": note.id,
        "invoice_number": note.invoice_number,
        "document_type": note.document_type,
        "parent_document_id": note.parent_document_id,
        "parent_invoice_number": parent.invoice_number,
        "parent_status": parent.status,
        "total_amount": note.total_amount,
        "status": note.status,
        "issued_at": note.issued_at,
    }


async def create_receipt(
    db: AsyncSession,
    tenant_id: UUID,
    parent_id: UUID,
    amount_paid: Decimal,
) -> dict:
    """Create a standalone Recibo for a partial or out-of-band payment.

    Unlike create_invoice_receipt, this does NOT transition the parent to paid.
    Use for partial payments or when the parent status is managed separately.
    """
    parent = await db.get(BillingDocument, parent_id)
    if not parent or parent.tenant_id != tenant_id:
        raise ApiError("parent_not_found", "Parent billing document not found", status_code=404)
    if parent.status not in ("issued", "overdue", "paid"):
        raise ApiError(
            "parent_invalid_status",
            f"Receipt can only be created against issued or paid documents"
            f" (parent status: {parent.status})",
            status_code=409,
        )

    now = datetime.now(UTC)
    note = BillingDocument(
        tenant_id=tenant_id,
        contract_id=parent.contract_id,
        client_id=getattr(parent, "client_id", None),
        client_name=parent.client_name,
        client_nuit=parent.client_nuit,
        contract_reference=parent.contract_reference,
        billing_period_start=parent.billing_period_start,
        billing_period_end=parent.billing_period_end,
        currency=parent.currency,
        subtotal=amount_paid,
        tax_amount=Decimal("0"),
        total_amount=amount_paid,
        document_type="receipt",
        parent_document_id=parent_id,
        parent_invoice_number=parent.invoice_number,
        issuer_name=parent.issuer_name,
        issuer_nuit=parent.issuer_nuit,
        status="issued",
        issued_at=now,
    )
    db.add(note)
    await db.flush()
    await _snapshot_profile(db, note, tenant_id)
    await _assign_invoice_number(db, note, tenant_id)

    await record_audit_log(
        db=db,
        tenant_id=tenant_id,
        action="billing.receipt_created",
        entity_type="billing_document",
        entity_id=note.id,
        new_values={
            "invoice_number": note.invoice_number,
            "parent_id": str(parent_id),
            "parent_invoice_number": parent.invoice_number,
            "amount_paid": str(note.total_amount),
            "document_type": "receipt",
        },
    )

    await db.commit()
    await db.refresh(note)

    return {
        "id": note.id,
        "invoice_number": note.invoice_number,
        "document_type": note.document_type,
        "parent_document_id": note.parent_document_id,
        "parent_invoice_number": parent.invoice_number,
        "amount_paid": note.total_amount,
        "status": note.status,
        "issued_at": note.issued_at,
    }


# ── FDOC-05: AR Básico ────────────────────────────────────────────────────────


def _compute_aging(document: BillingDocument, today: "datetime") -> dict:
    """Compute days_overdue and aging_bucket for a billing document."""
    due = document.due_date
    if not due or document.status not in ("issued", "overdue"):
        return {"days_overdue": 0, "aging_bucket": "current"}

    due_date_only = due.date()
    delta = (today.date() - due_date_only).days
    days_overdue = max(0, delta)

    if days_overdue == 0:
        bucket = "current"
    elif days_overdue <= 30:
        bucket = "1_30"
    elif days_overdue <= 60:
        bucket = "31_60"
    elif days_overdue <= 90:
        bucket = "61_90"
    else:
        bucket = "over_90"

    return {"days_overdue": days_overdue, "aging_bucket": bucket}


async def list_ar_documents(
    db: AsyncSession,
    tenant_id: UUID,
    aging_bucket: str | None = None,
    contract_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List issued billing_documents with due_date set (AR view).

    Filters by aging_bucket if provided. Returns documents ordered by due_date ASC
    (most urgent first). Only returns document_type='invoice' entries (not notes/receipts).
    """
    stmt = (
        select(BillingDocument)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status.in_(("issued", "overdue")),
            BillingDocument.due_date.isnot(None),
            BillingDocument.document_type == "invoice",
        )
        .order_by(BillingDocument.due_date.asc())
        .limit(limit)
        .offset(offset)
    )
    if contract_id:
        stmt = stmt.where(BillingDocument.contract_id == contract_id)

    result = await db.execute(stmt)
    docs = list(result.scalars())

    today = datetime.now(UTC)
    output = []
    for doc in docs:
        aging = _compute_aging(doc, today)
        if aging_bucket and aging["aging_bucket"] != aging_bucket:
            continue
        output.append(
            {
                "id": doc.id,
                "invoice_number": doc.invoice_number,
                "client_name": doc.client_name,
                "contract_id": doc.contract_id,
                "total_amount": doc.total_amount,
                "currency": doc.currency,
                "status": doc.status,
                "issued_at": doc.issued_at,
                "due_date": doc.due_date,
                "days_overdue": aging["days_overdue"],
                "aging_bucket": aging["aging_bucket"],
            }
        )
    return output


# ── D: AR Summary + Client Statement + Payments List ─────────────────────────


async def get_ar_summary(
    db: AsyncSession,
    tenant_id: UUID,
    as_of: "date | None" = None,
) -> dict:
    """GET /billing/ar/summary — totals per aging bucket in MZN.

    as_of: optional date to compute historical aging. When provided, only invoices
    with issued_at <= as_of are included and bucket assignment uses that date as
    the reference point. Defaults to today.
    """
    _as_of = as_of or datetime.now(UTC).date()
    today = datetime(_as_of.year, _as_of.month, _as_of.day, 23, 59, 59, tzinfo=UTC)

    stmt = select(BillingDocument).where(
        BillingDocument.tenant_id == tenant_id,
        BillingDocument.status.in_(("issued", "overdue")),
        BillingDocument.due_date.isnot(None),
        BillingDocument.document_type == "invoice",
        BillingDocument.issued_at <= today,
    )
    result = await db.execute(stmt)
    docs = list(result.scalars())

    buckets: dict[str, Decimal] = {
        "current": Decimal("0"),
        "1_30": Decimal("0"),
        "31_60": Decimal("0"),
        "61_90": Decimal("0"),
        "over_90": Decimal("0"),
    }
    for doc in docs:
        aging = _compute_aging(doc, today)
        bucket = aging["aging_bucket"]
        buckets[bucket] = (buckets[bucket] + (doc.total_amount or Decimal("0"))).quantize(
            Decimal("0.01")
        )

    total_ar = sum(buckets.values(), Decimal("0")).quantize(Decimal("0.01"))
    return {
        "current": buckets["current"],
        "1_30": buckets["1_30"],
        "31_60": buckets["31_60"],
        "61_90": buckets["61_90"],
        "over_90": buckets["over_90"],
        "total_ar": total_ar,
        "currency": "MZN",
        "as_of": _as_of.isoformat(),
    }


async def get_client_statement(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    as_of: "date | None" = None,
) -> dict:
    """GET /billing/clients/{client_id}/statement — balance and recent documents.

    as_of: optional date to filter documents. When provided, only documents with
    issued_at <= as_of are included. Each document includes amount_paid and outstanding
    computed from confirmed PaymentAllocation rows (voided payments excluded).
    """
    from app.modules.clients.models import Client  # avoid circular import at module level

    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError("client_not_found", "Client not found", status_code=404)

    _as_of_dt = (
        datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59, tzinfo=UTC)
        if as_of
        else datetime.now(UTC)
    )

    # Total invoiced = sum of issued/paid/overdue invoice totals for this client
    invoiced_result = await db.execute(
        select(func.coalesce(func.sum(BillingDocument.total_amount), 0)).where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.client_id == client_id,
            BillingDocument.document_type == "invoice",
            BillingDocument.status.in_(("issued", "paid", "overdue")),
            BillingDocument.issued_at <= _as_of_dt,
        )
    )
    total_invoiced = Decimal(str(invoiced_result.scalar_one())).quantize(Decimal("0.01"))

    # Total paid = sum of confirmed payment allocations for this client's invoices
    paid_result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0))
        .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
        .join(BillingDocument, BillingDocument.id == PaymentAllocation.billing_document_id)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.client_id == client_id,
            BillingDocument.issued_at <= _as_of_dt,
            ClientPayment.status == "confirmed",
        )
    )
    total_paid = Decimal(str(paid_result.scalar_one())).quantize(Decimal("0.01"))
    balance = (total_invoiced - total_paid).quantize(Decimal("0.01"))

    # Recent documents (last 50)
    docs_query_result = await db.execute(
        select(BillingDocument)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.client_id == client_id,
            BillingDocument.issued_at <= _as_of_dt,
        )
        .order_by(BillingDocument.created_at.desc())
        .limit(50)
    )
    docs_list = list(docs_query_result.scalars())

    # Bulk-fetch per-document confirmed payment allocations (single query, no N+1)
    doc_ids = [d.id for d in docs_list]
    paid_by_doc: dict[UUID, Decimal] = {}
    if doc_ids:
        alloc_result = await db.execute(
            select(
                PaymentAllocation.billing_document_id,
                func.coalesce(func.sum(PaymentAllocation.amount_applied), 0).label("paid"),
            )
            .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
            .where(
                PaymentAllocation.billing_document_id.in_(doc_ids),
                ClientPayment.status == "confirmed",
            )
            .group_by(PaymentAllocation.billing_document_id)
        )
        paid_by_doc = {
            row.billing_document_id: Decimal(str(row.paid)).quantize(Decimal("0.01"))
            for row in alloc_result
        }

    documents = []
    for d in docs_list:
        doc_paid = paid_by_doc.get(d.id, Decimal("0.00"))
        doc_outstanding = ((d.total_amount or Decimal("0")) - doc_paid).quantize(Decimal("0.01"))
        documents.append(
            {
                "id": d.id,
                "invoice_number": d.invoice_number,
                "document_type": d.document_type,
                "status": d.status,
                "total_amount": d.total_amount,
                "currency": d.currency,
                "issued_at": d.issued_at,
                "due_date": d.due_date,
                "amount_paid": doc_paid,
                "outstanding": doc_outstanding,
            }
        )

    return {
        "client_id": client_id,
        "client_name": client.trading_name,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "balance": balance,
        "currency": "MZN",
        "documents": documents,
        "as_of": as_of.isoformat() if as_of else None,
    }


async def get_top_debtors(
    db: AsyncSession,
    tenant_id: UUID,
    as_of: "date | None" = None,
    limit: int = 5,
) -> list[dict]:
    """Return clients ranked by outstanding balance descending.

    Outstanding = total_amount of issued/overdue invoices - confirmed allocations.
    Only status='issued' or 'overdue' docs with due_date set, document_type='invoice'.
    """
    from app.modules.clients.models import Client  # avoid circular import

    _as_of_dt = (
        datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59, tzinfo=UTC)
        if as_of
        else datetime.now(UTC)
    )

    # Fetch all relevant issued invoices for this tenant
    stmt = select(BillingDocument).where(
        BillingDocument.tenant_id == tenant_id,
        BillingDocument.status.in_(("issued", "overdue")),
        BillingDocument.due_date.isnot(None),
        BillingDocument.document_type == "invoice",
        BillingDocument.client_id.isnot(None),
        BillingDocument.issued_at <= _as_of_dt,
    )
    result = await db.execute(stmt)
    docs = list(result.scalars())
    if not docs:
        return []

    doc_ids = [d.id for d in docs]
    alloc_result = await db.execute(
        select(
            PaymentAllocation.billing_document_id,
            func.coalesce(func.sum(PaymentAllocation.amount_applied), 0).label("paid"),
        )
        .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.billing_document_id.in_(doc_ids),
            ClientPayment.status == "confirmed",
        )
        .group_by(PaymentAllocation.billing_document_id)
    )
    paid_by_doc: dict = {row.billing_document_id: Decimal(str(row.paid)) for row in alloc_result}

    # Aggregate by client_id
    client_outstanding: dict = {}
    client_worst_bucket: dict = {}
    today_for_aging = _as_of_dt

    for doc in docs:
        cid = doc.client_id
        paid = paid_by_doc.get(doc.id, Decimal("0"))
        outstanding = (doc.total_amount or Decimal("0")) - paid
        if outstanding <= Decimal("0"):
            continue
        client_outstanding[cid] = client_outstanding.get(cid, Decimal("0")) + outstanding
        aging = _compute_aging(doc, today_for_aging)
        existing = client_worst_bucket.get(cid, "current")
        # bucket severity order: current < 1_30 < 31_60 < 61_90 < over_90
        _order = {"current": 0, "1_30": 1, "31_60": 2, "61_90": 3, "over_90": 4}
        if _order.get(aging["aging_bucket"], 0) > _order.get(existing, 0):
            client_worst_bucket[cid] = aging["aging_bucket"]

    # Sort by outstanding desc, take top N
    ranked = sorted(client_outstanding.items(), key=lambda x: x[1], reverse=True)[:limit]

    # Bulk-fetch client names
    client_ids = [cid for cid, _ in ranked]
    clients_result = await db.execute(
        select(Client).where(Client.id.in_(client_ids), Client.tenant_id == tenant_id)
    )
    clients_map = {c.id: c for c in clients_result.scalars()}

    return [
        {
            "client_id": str(cid),
            "client_name": clients_map[cid].trading_name if cid in clients_map else "—",
            "outstanding": outstanding.quantize(Decimal("0.01")),
            "worst_bucket": client_worst_bucket.get(cid, "current"),
        }
        for cid, outstanding in ranked
        if cid in clients_map
    ]


async def generate_client_statement_pdf(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
    as_of: "date | None" = None,
) -> bytes:
    """Generate a PDF client statement using fpdf2 + DejaVuSans (same pattern as exporters.py).

    Header: tenant issuer_name + issuer_nuit (fallback tenant.name)
    Client block: name, NUIT if available
    Table: invoice_number | issue_date | due_date | total | paid | outstanding | status
    Footer: total outstanding balance, currency MZN
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    from app.modules.billing.exporters import FONTS_DIR
    from app.modules.clients.models import Client

    # Fetch client
    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError("client_not_found", "Client not found", status_code=404)

    # Get statement data (reuses the extended get_client_statement)
    stmt_data = await get_client_statement(db, tenant_id, client_id, as_of=as_of)

    # Determine issuer info from most recent issued document or tenant fallback
    tenant = await db.get(Tenant, tenant_id)
    issuer_name = tenant.name if tenant else "ROTAS"
    issuer_nuit = getattr(tenant, "nuit", None)

    # Try to find issuer_name/issuer_nuit from an issued billing document
    from sqlalchemy import select as sa_select

    doc_row = await db.execute(
        sa_select(BillingDocument)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status.in_(("issued", "paid", "overdue")),
            BillingDocument.issuer_name.isnot(None),
        )
        .order_by(BillingDocument.issued_at.desc())
        .limit(1)
    )
    doc_sample = doc_row.scalar_one_or_none()
    if doc_sample and doc_sample.issuer_name:
        issuer_name = doc_sample.issuer_name
        issuer_nuit = doc_sample.issuer_nuit

    _as_of_label = as_of.isoformat() if as_of else datetime.now(UTC).date().isoformat()

    # Build PDF — brand palette (same constants as exporters.py)
    _NAV = (16, 32, 51)
    _SOFT = (245, 247, 250)
    _LINE = (216, 222, 232)
    _INK = (23, 32, 51)
    _MUTED = (102, 112, 133)
    _WHITE = (255, 255, 255)

    class _StatementPDF(FPDF):
        def header(self):
            self.set_fill_color(*_NAV)
            self.rect(0, 0, 210, 22, "F")
            self.set_y(4)
            self.set_text_color(*_WHITE)
            self.set_font("DejaVu", "B", 16)
            self.cell(0, 8, issuer_name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if issuer_nuit:
                self.set_font("DejaVu", "", 7)
                self.set_y(12)
                self.cell(0, 4, f"NUIT {issuer_nuit}", align="L")
            self.set_fill_color(*_SOFT)
            self.set_draw_color(*_LINE)
            self.rect(0, 22, 210, 12, "FD")
            self.set_y(25)
            self.set_text_color(*_INK)
            self.set_font("DejaVu", "B", 11)
            self.cell(0, 6, "EXTRATO DE CONTA CORRENTE", align="C")
            self.set_font("DejaVu", "", 7)
            self.set_text_color(*_MUTED)
            self.set_y(25)
            self.cell(0, 3, f"Referência: {_as_of_label}", align="R")
            self.set_y(36)
            self.set_text_color(*_INK)

        def footer(self):
            self.set_y(-14)
            self.set_draw_color(*_LINE)
            self.set_line_width(0.3)
            self.line(15, self.get_y(), 195, self.get_y())
            self.set_y(-12)
            self.set_font("DejaVu", "", 7)
            self.set_text_color(*_MUTED)
            self.cell(0, 5, issuer_name, align="L")
            self.cell(0, 5, f"Página {self.page_no()}", align="R")

    pdf = _StatementPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()

    # Client block
    def _row(label: str, value: str):
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(35, 5, label.upper(), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _row("Cliente", stmt_data["client_name"] or "—")
    if client.nuit:
        _row("NUIT", client.nuit)
    _row("Referência", _as_of_label)
    pdf.ln(4)

    # Table columns: Fatura | Emissão | Vencimento | Total | Pago | Em Aberto | Estado
    COL_W = [28, 22, 22, 30, 30, 30, 18]  # = 180mm usable
    HEADERS = [
        "Fatura",
        "Emissão",
        "Vencimento",
        "Total MZN",
        "Pago MZN",
        "Em Aberto MZN",
        "Estado",
    ]
    ALIGN = ["L", "C", "C", "R", "R", "R", "C"]

    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7.5)
    for w, label, align in zip(COL_W, HEADERS, ALIGN, strict=False):
        pdf.cell(w, 7, label, border=0, fill=True, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    # Data rows
    pdf.set_font("DejaVu", "", 7.5)
    _status_pt = {
        "issued": "Emitido",
        "overdue": "Vencido",
        "paid": "Pago",
        "draft": "Rascunho",
        "cancelled": "Cancelado",
    }

    for idx, doc in enumerate(stmt_data["documents"]):
        fill = idx % 2 == 0
        pdf.set_fill_color(*(_SOFT if fill else _WHITE))
        pdf.set_text_color(*_INK)

        inv_num = doc.get("invoice_number") or "—"
        issued = doc.get("issued_at")
        due = doc.get("due_date")
        total = Decimal(str(doc.get("total_amount") or 0))
        paid = Decimal(str(doc.get("amount_paid") or 0))
        outstanding = Decimal(str(doc.get("outstanding") or 0))
        raw_status = str(doc.get("status") or "")
        status_label = _status_pt.get(raw_status, raw_status)

        def _fmt_date(d) -> str:
            if not d:
                return "—"
            if hasattr(d, "strftime"):
                return d.strftime("%d/%m/%Y")
            try:
                return str(d)[:10]
            except Exception:
                return "—"

        values = [
            (inv_num[:16], "L"),
            (_fmt_date(issued), "C"),
            (_fmt_date(due), "C"),
            (f"{total:,.2f}", "R"),
            (f"{paid:,.2f}", "R"),
            (f"{outstanding:,.2f}", "R"),
            (status_label[:10], "C"),
        ]
        for w, (cell_text, align) in zip(COL_W, values, strict=False):
            pdf.cell(  # noqa: E501
                w,
                6,
                cell_text,
                border=0,
                fill=fill,
                align=align,
                new_x=XPos.RIGHT,
                new_y=YPos.TOP,
            )
        pdf.ln()

    # Summary totals
    pdf.ln(4)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    total_outstanding = Decimal(str(stmt_data["balance"] or 0))
    label_w = sum(COL_W[:4])
    val_w = sum(COL_W[4:])

    pdf.set_fill_color(*_SOFT)
    pdf.set_text_color(*_INK)
    pdf.set_font("DejaVu", "", 9)
    pdf.cell(label_w, 7, "Total Emitido", fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        val_w,
        7,
        f"{Decimal(str(stmt_data['total_invoiced'])):,.2f} MZN",
        fill=True,
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_fill_color(*_SOFT)
    pdf.cell(label_w, 7, "Total Recebido", fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        val_w,
        7,
        f"{Decimal(str(stmt_data['total_paid'])):,.2f} MZN",
        fill=True,
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(label_w, 7, "SALDO EM ABERTO", fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        val_w,
        7,
        f"{total_outstanding:,.2f} MZN",
        fill=True,
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    return bytes(pdf.output())


async def list_payments(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    client_id: UUID | None = None,
    status: str | None = None,
    value_date_start: datetime | None = None,
    value_date_end: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """GET /billing/payments — paginated list with optional filters."""
    query = (
        select(ClientPayment)
        .where(ClientPayment.tenant_id == tenant_id)
        .order_by(ClientPayment.created_at.desc())
    )
    if client_id:
        query = query.where(ClientPayment.client_id == client_id)
    if status:
        query = query.where(ClientPayment.status == status)
    if value_date_start:
        query = query.where(ClientPayment.value_date >= value_date_start)
    if value_date_end:
        query = query.where(ClientPayment.value_date < value_date_end)

    count_query = select(func.count(ClientPayment.id)).where(ClientPayment.tenant_id == tenant_id)
    if client_id:
        count_query = count_query.where(ClientPayment.client_id == client_id)
    if status:
        count_query = count_query.where(ClientPayment.status == status)
    if value_date_start:
        count_query = count_query.where(ClientPayment.value_date >= value_date_start)
    if value_date_end:
        count_query = count_query.where(ClientPayment.value_date < value_date_end)

    total = await db.scalar(count_query) or 0
    rows = await db.execute(query.limit(limit).offset(offset))
    payments = list(rows.scalars())

    # Bulk-fetch allocations for all payments in one query
    payment_ids = [p.id for p in payments]
    alloc_map: dict = {}
    if payment_ids:
        alloc_rows = await db.execute(
            select(PaymentAllocation).where(PaymentAllocation.payment_id.in_(payment_ids))
        )
        for a in alloc_rows.scalars():
            alloc_map.setdefault(a.payment_id, []).append(a)

    return {
        "items": [serialize_payment(p, alloc_map.get(p.id, [])) for p in payments],
        "total": int(total),
    }


# ── Phase 6: Payment Registration Service Functions ───────────────────────────


async def _sum_confirmed_allocations(
    db: AsyncSession, tenant_id: UUID, billing_document_id: UUID
) -> Decimal:
    """Sum amount_applied for confirmed payments allocated to this billing document."""
    result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0))
        .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.billing_document_id == billing_document_id,
            ClientPayment.tenant_id == tenant_id,
            ClientPayment.status == "confirmed",
        )
    )
    return Decimal(str(result.scalar_one())).quantize(Decimal("0.01"))


def serialize_payment(payment: ClientPayment, allocations: list) -> dict:
    return {
        "id": str(payment.id),  # str — test_payment_idempotency: str(rows[0].id) == result["id"]
        "tenant_id": payment.tenant_id,
        "client_id": payment.client_id,
        "billing_document_id": payment.billing_document_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "value_date": payment.value_date,
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "notes": payment.notes,
        "status": payment.status,
        "voided_at": payment.voided_at,
        "voided_by": payment.voided_by,
        "void_reason": payment.void_reason,
        "created_by": payment.created_by,
        "created_at": payment.created_at,
        "allocations": [
            {
                "id": a.id,
                "billing_document_id": a.billing_document_id,
                "amount_applied": a.amount_applied,
                "created_at": a.created_at,
            }
            for a in allocations
        ],
    }


async def register_payment(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID | None,
    payload,  # ClientPaymentCreate — imported inline to avoid circular import at module level
) -> dict:
    """PAY-01 / PAY-02: Register a client payment, optionally allocating it to an invoice.

    If billing_document_id is None, creates an advance payment (no allocation row).
    If billing_document_id is provided, verifies tenant + client match, guards over-allocation,
    creates PaymentAllocation, and transitions the document to 'paid' when fully covered.
    """
    from app.modules.clients.models import Client  # avoid circular import

    # 1. Verify client belongs to this tenant
    client = await db.get(Client, payload.client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError("client_not_found", "Client not found", status_code=404)

    billing_doc = None
    if payload.billing_document_id:
        # 2a. Verify billing document belongs to tenant (with FOR UPDATE lock to prevent allocation races)
        billing_doc = await db.scalar(
            select(BillingDocument)
            .where(
                BillingDocument.id == payload.billing_document_id,
                BillingDocument.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if not billing_doc:
            raise ApiError("billing_document_not_found", "Invoice not found", status_code=404)
        # 2b. Cross-client mismatch guard
        if billing_doc.client_id != payload.client_id:
            raise ApiError(
                "payment_client_mismatch",
                "Payment client does not match invoice client",
                status_code=409,
            )
        # 2c. Invoice must be payable
        if billing_doc.status not in ("issued", "overdue"):
            raise ApiError(
                "invoice_not_payable",
                f"Invoice status '{billing_doc.status}' does not accept payments",
                status_code=409,
            )
        # 2d. Over-allocation guard
        existing_paid = await _sum_confirmed_allocations(db, tenant_id, billing_doc.id)
        remaining = (billing_doc.total_amount - existing_paid).quantize(Decimal("0.01"))
        if payload.amount > remaining:
            raise ApiError(
                "payment_exceeds_invoice_balance",
                "Payment amount exceeds remaining invoice balance",
                status_code=409,
                details={"remaining": str(remaining), "requested": str(payload.amount)},
            )

    # 3. Create payment record
    payment = ClientPayment(
        tenant_id=tenant_id,
        client_id=payload.client_id,
        billing_document_id=payload.billing_document_id,
        amount=payload.amount,
        currency=getattr(payload, "currency", "MZN") or "MZN",
        value_date=payload.value_date,
        payment_method=payload.payment_method,
        reference=getattr(payload, "reference", None),
        notes=getattr(payload, "notes", None),
        status="confirmed",
        created_by=user_id,
    )
    db.add(payment)
    await db.flush()

    allocations: list[PaymentAllocation] = []
    if billing_doc:
        # 4. Create allocation row
        alloc = PaymentAllocation(
            tenant_id=tenant_id,
            payment_id=payment.id,
            billing_document_id=billing_doc.id,
            amount_applied=payload.amount,
        )
        db.add(alloc)
        allocations.append(alloc)
        await db.flush()

        # 5. Transition document to 'paid' if fully covered
        new_total_paid = (existing_paid + payload.amount).quantize(Decimal("0.01"))
        if new_total_paid >= billing_doc.total_amount:
            await transition_billing_document(
                db,
                document=billing_doc,
                new_status="paid",
                user_id=user_id,
                tenant_id=tenant_id,
                paid_at=payload.value_date,
            )

    # 6. Audit log
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="payment.created",
        entity_type="client_payment",
        entity_id=payment.id,
        new_values={
            "client_id": str(payload.client_id),
            "billing_document_id": (
                str(payload.billing_document_id) if payload.billing_document_id else None
            ),
            "amount": str(payload.amount),
            "payment_method": payload.payment_method,
        },
    )
    await db.commit()
    await db.refresh(payment)
    for a in allocations:
        await db.refresh(a)
    return serialize_payment(payment, allocations)


async def void_payment(
    db: AsyncSession,
    *,
    payment_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    void_reason: str,
) -> dict:
    """PAY-01 / PAY-03: Void a confirmed payment and reverse any billing document transitions.

    Sets status='voided'. For each affected billing document, if the remaining confirmed
    allocations no longer cover the total_amount and the document is 'paid', it is reverted
    to 'issued' or 'overdue' (depending on due_date).
    """
    # 1. Fetch + verify
    payment = await db.get(ClientPayment, payment_id)
    if not payment or payment.tenant_id != tenant_id:
        raise ApiError("payment_not_found", "Payment not found", status_code=404)

    # 2. Must be confirmed to void
    if payment.status != "confirmed":
        raise ApiError(
            "payment_already_voided",
            "Payment has already been voided",
            status_code=409,
        )

    # 3. Collect affected billing document IDs before voiding
    alloc_result = await db.execute(
        select(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id)
    )
    allocations = list(alloc_result.scalars())
    affected_doc_ids = [a.billing_document_id for a in allocations]

    # 4. Void the payment
    payment.status = "voided"
    payment.voided_at = datetime.now(UTC)
    payment.voided_by = user_id
    payment.void_reason = void_reason
    db.add(payment)
    await db.flush()

    # 5. For each affected billing document, check if it needs to revert from 'paid'
    for doc_id in affected_doc_ids:
        billing_doc = await db.get(BillingDocument, doc_id)
        if not billing_doc:
            continue
        if billing_doc.status != "paid":
            continue
        # Re-compute remaining confirmed allocations (payment is now voided so excluded)
        remaining_allocated = await _sum_confirmed_allocations(db, tenant_id, doc_id)
        if remaining_allocated < billing_doc.total_amount:
            # Determine correct revert status
            now = datetime.now(UTC)
            due = billing_doc.due_date
            # Normalise due_date to timezone-aware if naive
            if due is not None and due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            revert_status = "overdue" if (due is not None and due < now) else "issued"
            # transition_billing_document only allows paid→(none), so we set manually
            # because 'paid' is a terminal state in the SM — we bypass the guard here
            # since voiding is an exceptional financial reversal path.
            old_status = billing_doc.status
            billing_doc.status = revert_status
            billing_doc.paid_at = None
            db.add(billing_doc)
            await db.flush()
            # Record audit log for the reversal
            await record_audit_log(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                action=f"billing.document.{revert_status}",
                entity_type="billing_document",
                entity_id=billing_doc.id,
                old_values={"status": old_status},
                new_values={"status": revert_status, "paid_at": None},
            )

    # 6. Audit log for void
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="payment.voided",
        entity_type="client_payment",
        entity_id=payment.id,
        old_values={"status": "confirmed"},
        new_values={"status": "voided", "void_reason": void_reason},
    )
    await db.commit()
    await db.refresh(payment)
    return serialize_payment(payment, allocations)


async def apply_advance_to_invoice(
    db: AsyncSession,
    *,
    payment_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None,
    billing_document_id: UUID,
    amount_applied: Decimal,
) -> dict:
    """PAY-02: Apply an advance payment (billing_document_id=None) to a specific invoice.

    Verifies the payment is a true advance, checks over-application guard on both
    the payment side and the invoice side, creates a PaymentAllocation row, and
    transitions the document to 'paid' if fully covered.
    """
    # 1. Fetch + verify payment
    payment = await db.get(ClientPayment, payment_id)
    if not payment or payment.tenant_id != tenant_id:
        raise ApiError("payment_not_found", "Payment not found", status_code=404)
    if payment.status != "confirmed":
        raise ApiError(
            "payment_not_confirmed",
            "Only confirmed payments can be applied",
            status_code=409,
        )
    if payment.billing_document_id is not None:
        raise ApiError(
            "payment_not_an_advance",
            "Only advance payments (no initial billing_document_id) can be applied this way",
            status_code=409,
        )

    # 2. Fetch + verify billing document
    billing_doc = await db.get(BillingDocument, billing_document_id)
    if not billing_doc or billing_doc.tenant_id != tenant_id:
        raise ApiError("billing_document_not_found", "Invoice not found", status_code=404)
    if billing_doc.client_id != payment.client_id:
        raise ApiError(
            "payment_client_mismatch",
            "Payment client does not match invoice client",
            status_code=409,
        )
    if billing_doc.status not in ("issued", "overdue"):
        raise ApiError(
            "invoice_not_payable",
            f"Invoice status '{billing_doc.status}' does not accept payments",
            status_code=409,
        )

    # 3. Guard: advance over-application (don't allocate more than payment total)
    existing_alloc_result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0)).where(
            PaymentAllocation.payment_id == payment_id
        )
    )
    already_applied = Decimal(str(existing_alloc_result.scalar_one())).quantize(Decimal("0.01"))
    if already_applied + amount_applied > payment.amount:
        raise ApiError(
            "advance_over_applied",
            "Total applied would exceed original payment amount",
            status_code=409,
            details={
                "payment_amount": str(payment.amount),
                "already_applied": str(already_applied),
                "requested": str(amount_applied),
            },
        )

    # 4. Guard: don't exceed invoice remaining balance
    doc_already_paid = await _sum_confirmed_allocations(db, tenant_id, billing_document_id)
    doc_remaining = (billing_doc.total_amount - doc_already_paid).quantize(Decimal("0.01"))
    if amount_applied > doc_remaining:
        raise ApiError(
            "payment_exceeds_invoice_balance",
            "Amount applied exceeds remaining invoice balance",
            status_code=409,
            details={"remaining": str(doc_remaining), "requested": str(amount_applied)},
        )

    # 5. Create allocation
    alloc = PaymentAllocation(
        tenant_id=tenant_id,
        payment_id=payment_id,
        billing_document_id=billing_document_id,
        amount_applied=amount_applied,
    )
    db.add(alloc)
    await db.flush()

    # 6. Transition document to 'paid' if fully covered
    new_doc_total_paid = (doc_already_paid + amount_applied).quantize(Decimal("0.01"))
    if new_doc_total_paid >= billing_doc.total_amount:
        await transition_billing_document(
            db,
            document=billing_doc,
            new_status="paid",
            user_id=user_id,
            tenant_id=tenant_id,
            paid_at=payment.value_date,
        )

    # 7. Audit log
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="payment.advance_applied",
        entity_type="client_payment",
        entity_id=payment_id,
        new_values={
            "billing_document_id": str(billing_document_id),
            "amount_applied": str(amount_applied),
        },
    )
    await db.commit()
    await db.refresh(payment)

    # Return updated payment with all allocations
    all_alloc_result = await db.execute(
        select(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id)
    )
    all_allocations = list(all_alloc_result.scalars())
    return serialize_payment(payment, all_allocations)
