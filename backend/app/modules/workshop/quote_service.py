from datetime import datetime, UTC
from decimal import Decimal
from uuid import UUID

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder, WorkOrderTask
from app.modules.workshop.quote_models import WorkshopQuote, WorkshopQuoteItem
from app.modules.workshop.quote_schemas import QuoteCreate
from app.modules.workshop.reception_service import get_next_tenant_sequence


def serialize_quote_item(item: WorkshopQuoteItem) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "quote_id": item.quote_id,
        "item_type": item.item_type,
        "description": item.description,
        "part_id": item.part_id,
        "quantity": float(item.quantity),
        "unit_price": float(item.unit_price),
        "total_price": float(item.total_price),
        "warranty_months": item.warranty_months,
        "warranty_km": item.warranty_km,
        "created_at": item.created_at,
    }


def serialize_quote(quote: WorkshopQuote, items: list[dict] | None = None) -> dict:
    return {
        "id": quote.id,
        "tenant_id": quote.tenant_id,
        "vehicle_id": quote.vehicle_id,
        "client_id": quote.client_id,
        "reception_id": quote.reception_id,
        "quote_number": quote.quote_number,
        "is_supplemental": quote.is_supplemental,
        "related_work_order_id": quote.related_work_order_id,
        "status": quote.status,
        "valid_until": quote.valid_until,
        "labor_total": float(quote.labor_total),
        "parts_total": float(quote.parts_total),
        "tax_total": float(quote.tax_total),
        "total_amount": float(quote.total_amount),
        "notes": quote.notes,
        "client_signature_file_id": quote.client_signature_file_id,
        "acceptance_channel": quote.acceptance_channel,
        "accepted_by_person_name": quote.accepted_by_person_name,
        "items": items or [],
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
    }


async def create_quote(
    db: AsyncSession,
    tenant_id: UUID,
    payload: QuoteCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    if payload.is_supplemental:
        if not payload.related_work_order_id:
            raise ApiError(
                "invalid_supplemental_quote",
                "Supplemental quote requires related_work_order_id.",
                status_code=400,
            )
        target_wo = await db.get(WorkOrder, payload.related_work_order_id)
        if not target_wo or target_wo.tenant_id != tenant_id:
            raise ApiError("work_order_not_found", "Related Work Order not found.", status_code=404)

    current_year = datetime.now(UTC).year
    seq_num = await get_next_tenant_sequence(db, tenant_id, "quote")
    quote_number = f"ORC-{current_year}-{seq_num:04d}"

    labor_total = Decimal("0")
    parts_total = Decimal("0")

    quote = WorkshopQuote(
        tenant_id=tenant_id,
        vehicle_id=payload.vehicle_id,
        client_id=payload.client_id or getattr(vehicle, "customer_client_id", None),
        reception_id=payload.reception_id,
        quote_number=quote_number,
        is_supplemental=payload.is_supplemental,
        related_work_order_id=payload.related_work_order_id,
        status="sent",  # Envia logo por omissão
        valid_until=payload.valid_until,
        tax_total=payload.tax_total,
        notes=payload.notes,
    )
    db.add(quote)
    await db.flush()

    quote_items = []
    for item_in in payload.items:
        line_total = Decimal(str(item_in.quantity)) * Decimal(str(item_in.unit_price))
        if item_in.item_type == "labor":
            labor_total += line_total
        else:
            parts_total += line_total

        item = WorkshopQuoteItem(
            tenant_id=tenant_id,
            quote_id=quote.id,
            item_type=item_in.item_type,
            description=item_in.description,
            part_id=item_in.part_id,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            total_price=line_total,
            warranty_months=item_in.warranty_months,
            warranty_km=item_in.warranty_km,
        )
        db.add(item)
        quote_items.append(item)

    quote.labor_total = labor_total
    quote.parts_total = parts_total
    quote.total_amount = labor_total + parts_total + payload.tax_total

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_quote.created",
        entity_type="workshop_quote",
        entity_id=quote.id,
        new_values={"quote_number": quote.quote_number, "total_amount": float(quote.total_amount)},
    )
    await db.commit()
    await db.refresh(quote)

    items_res = [serialize_quote_item(it) for it in quote_items]
    return serialize_quote(quote, items=items_res)


async def list_quotes(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(WorkshopQuote).where(WorkshopQuote.tenant_id == tenant_id)
    if status_filter:
        query = query.where(WorkshopQuote.status == status_filter)
    if vehicle_id:
        query = query.where(WorkshopQuote.vehicle_id == vehicle_id)

    res = await db.execute(query.order_by(WorkshopQuote.created_at.desc()).limit(limit).offset(offset))
    quotes = res.scalars().all()
    return [serialize_quote(q) for q in quotes]


async def get_quote_detail(db: AsyncSession, tenant_id: UUID, quote_id: UUID) -> dict:
    quote = await db.get(WorkshopQuote, quote_id)
    if not quote or quote.tenant_id != tenant_id:
        raise ApiError("quote_not_found", "Quote not found.", status_code=404)

    items_res = await db.execute(
        select(WorkshopQuoteItem)
        .where(WorkshopQuoteItem.quote_id == quote_id, WorkshopQuoteItem.tenant_id == tenant_id)
    )
    items = [serialize_quote_item(it) for it in items_res.scalars().all()]
    return serialize_quote(quote, items=items)


async def accept_quote(
    db: AsyncSession,
    tenant_id: UUID,
    quote_id: UUID,
    *,
    acceptance_channel: str | None = None,
    accepted_by_person_name: str | None = None,
    actor_id: UUID | None = None,
) -> dict:
    """Aceita o orçamento com LOCK FOR UPDATE no registo da quote para prevenir race condition.
    - Se a quote for suplementar, não cria WorkOrder nova — anexa os itens à OS existente.
    - Se for a quote inicial, cria a nova WorkOrder (OS-2026-XXXX) no ramo else.
    """
    stmt = (
        select(WorkshopQuote)
        .where(WorkshopQuote.id == quote_id, WorkshopQuote.tenant_id == tenant_id)
        .with_for_update()
    )
    res = await db.execute(stmt)
    quote = res.scalar_one_or_none()

    if not quote:
        raise ApiError("quote_not_found", "Quote not found.", status_code=404)

    if quote.status == "converted":
        raise ApiError("quote_already_converted", "Quote has already been accepted.", status_code=409)

    if quote.status != "sent":
        raise ApiError(
            "invalid_quote_status",
            f"Quote cannot be accepted from status '{quote.status}'.",
            status_code=400,
        )

    # Fetch quote items
    items_stmt = select(WorkshopQuoteItem).where(
        WorkshopQuoteItem.quote_id == quote_id, WorkshopQuoteItem.tenant_id == tenant_id
    )
    items_res = await db.execute(items_stmt)
    quote_items = items_res.scalars().all()

    if quote.is_supplemental and quote.related_work_order_id:
        # Ramo Suplementar — reutiliza a OS existente
        target_wo = await db.get(WorkOrder, quote.related_work_order_id)
        if not target_wo or target_wo.tenant_id != tenant_id:
            raise ApiError("work_order_not_found", "Target Work Order not found.", status_code=404)
        target_wo_id = target_wo.id

        # Adiciona tarefas suplementares à OS
        for it in quote_items:
            task = WorkOrderTask(
                tenant_id=tenant_id,
                work_order_id=target_wo_id,
                description=f"[Suplementar {quote.quote_number}] {it.description}",
                status="pending",
            )
            db.add(task)
    else:
        # Ramo Orçamento Inicial — cria a WorkOrder nova AQUI DENTRO DO ELSE!
        current_year = datetime.now(UTC).year
        wo_seq = await get_next_tenant_sequence(db, tenant_id, "work_order")
        wo_number = f"OS-{current_year}-{wo_seq:04d}"

        new_wo = WorkOrder(
            tenant_id=tenant_id,
            vehicle_id=quote.vehicle_id,
            reception_id=quote.reception_id,
            work_order_number=wo_number,
            planned_work=quote.notes or f"Reparação baseada no Orçamento {quote.quote_number}",
            estimated_cost=quote.total_amount,
            status="approved",  # Já começa aprovada via orçamento
            origin_type="quote",
            labor_cost=quote.labor_total,
        )
        db.add(new_wo)
        await db.flush()
        target_wo_id = new_wo.id

        # Adiciona tarefas base da quote à nova OS
        for it in quote_items:
            task = WorkOrderTask(
                tenant_id=tenant_id,
                work_order_id=target_wo_id,
                description=it.description,
                status="pending",
            )
            db.add(task)

    # Link quote to the target work order and set status to converted
    quote.related_work_order_id = target_wo_id
    quote.status = "converted"
    if acceptance_channel:
        quote.acceptance_channel = acceptance_channel
    if accepted_by_person_name:
        quote.accepted_by_person_name = accepted_by_person_name
    await db.flush()

    # Create part stock reservations for this quote and WO
    from app.modules.workshop.inventory_service import create_part_reservations
    await create_part_reservations(db, tenant_id, quote.id, target_wo_id)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_quote.accepted",
        entity_type="workshop_quote",
        entity_id=quote.id,
        new_values={"status": "converted", "work_order_id": str(target_wo_id)},
    )
    await db.commit()
    await db.refresh(quote)

    return {
        "quote": serialize_quote(quote),
        "work_order_id": target_wo_id,
    }


async def reject_quote(
    db: AsyncSession,
    tenant_id: UUID,
    quote_id: UUID,
    reason: str | None = None,
    *,
    actor_id: UUID | None = None,
) -> dict:
    quote = await db.get(WorkshopQuote, quote_id)
    if not quote or quote.tenant_id != tenant_id:
        raise ApiError("quote_not_found", "Quote not found.", status_code=404)

    if quote.status != "sent":
        raise ApiError(
            "invalid_quote_status",
            f"Quote cannot be rejected from status '{quote.status}'.",
            status_code=400,
        )

    quote.status = "rejected"
    if reason:
        quote.notes = f"{quote.notes or ''}\nMotivo rejeição: {reason}".strip()
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_quote.rejected",
        entity_type="workshop_quote",
        entity_id=quote.id,
        new_values={"status": "rejected", "reason": reason},
    )
    await db.commit()
    await db.refresh(quote)
    return serialize_quote(quote)


async def expire_outdated_quotes(db: AsyncSession) -> int:
    """Worker background agendado (ARQ) que expira orçamentos passados da data de validade."""
    now = datetime.now(UTC)
    stmt = (
        update(WorkshopQuote)
        .where(
            WorkshopQuote.status == "sent",
            WorkshopQuote.valid_until.is_not(None),
            WorkshopQuote.valid_until < now,
        )
        .values(status="expired")
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount
