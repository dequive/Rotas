"""Workshop Inventory & Parts Service — lógica avançada de peças, consumíveis e reservas.

Funcionalidades:
  - Disponibilidade de Stock (`get_available_stock` = current_quantity - active_reservations).
  - Reserva de Stock no Orçamento (`create_part_reservations`).
  - Entrega Fracionada de Peças/Óleos (`issue_parts_for_work_order`) com lock FOR UPDATE,
    verificação de tecto aprovado (HTTP 409 se requested_qty > approved_ceiling),
    e consumo FIFO determinístico de reservas (created_at ASC, id ASC) com libertação do excesso.
  - Devolução OS → Stock (`return_part_from_work_order`) com guarda 409 contra OS fechada/facturada.
  - Cancelamento de OS (`cancel_work_order`) com libertação de reservas órfãs e anulação de invoice draft.
  - Ajuste de Inventário (`record_inventory_adjustment`) com permissão explícita e audit log.
  - Reposição Inteligente (`get_reorder_suggestions`) e Valorização de Stock (`get_inventory_valuation_summary`).
  - Encomendas a Fornecedores (`PurchaseOrder`) e Peças Velhas em Retoma (`CoreReturnItem`).
"""

import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.billing.models import BillingDocument
from app.modules.third_party.models import ThirdParty
from app.modules.workshop.models import (
    CoreReturnItem,
    MaintenancePartUsed,
    PartReservation,
    WorkshopPurchaseOrder,
    WorkshopPurchaseOrderItem,
    SparePartInventory,
    SparePartMovement,
    SparePartRequisition,
    WorkOrder,
    WorkOrderTask,
)
from app.modules.workshop.quote_models import WorkshopQuote, WorkshopQuoteItem


async def get_available_stock(
    db: AsyncSession,
    tenant_id: UUID,
    inventory_id: UUID,
) -> Decimal:
    """Calcula o stock disponível real = current_quantity - SUM(quantity_reserved ativa)."""
    item = await db.scalar(
        select(SparePartInventory).where(
            SparePartInventory.id == inventory_id,
            SparePartInventory.tenant_id == tenant_id,
        )
    )
    if not item:
        raise ApiError("part_not_found", "Spare part inventory item not found.", status_code=404)

    active_res = await db.scalar(
        select(func.coalesce(func.sum(PartReservation.quantity_reserved), Decimal("0"))).where(
            PartReservation.tenant_id == tenant_id,
            PartReservation.inventory_id == inventory_id,
            PartReservation.status == "active",
        )
    )
    res_qty = Decimal(str(active_res))
    available = (item.current_quantity - res_qty).quantize(Decimal("0.001"))
    return max(available, Decimal("0.000"))


async def create_part_reservations(
    db: AsyncSession,
    tenant_id: UUID,
    quote_id: UUID,
    work_order_id: UUID | None = None,
) -> list[PartReservation]:
    """Cria reservas de stock para itens do tipo 'part' de um orçamento aceite.

    Executa sob LOCK FOR UPDATE nos itens de inventário para prevenir race conditions.
    Se o stock disponível for insuficiente para algum item, a reserva é criada com status='active_backorder'.
    """
    quote_items_res = await db.execute(
        select(WorkshopQuoteItem).where(
            WorkshopQuoteItem.quote_id == quote_id,
            WorkshopQuoteItem.tenant_id == tenant_id,
            WorkshopQuoteItem.item_type == "part",
            WorkshopQuoteItem.part_id.isnot(None),
        )
    )
    quote_items = quote_items_res.scalars().all()
    reservations: list[PartReservation] = []

    for qi in quote_items:
        if not qi.part_id or qi.quantity <= 0:
            continue

        # Lock FOR UPDATE on inventory item
        inv = await db.scalar(
            select(SparePartInventory)
            .where(
                SparePartInventory.id == qi.part_id,
                SparePartInventory.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if not inv:
            continue

        # Calculate current active reservations for this part
        active_res = await db.scalar(
            select(func.coalesce(func.sum(PartReservation.quantity_reserved), Decimal("0"))).where(
                PartReservation.tenant_id == tenant_id,
                PartReservation.inventory_id == qi.part_id,
                PartReservation.status == "active",
            )
        )
        avail = inv.current_quantity - Decimal(str(active_res))
        status = "active" if avail >= qi.quantity else "active_backorder"

        res = PartReservation(
            tenant_id=tenant_id,
            inventory_id=qi.part_id,
            quote_id=quote_id,
            work_order_id=work_order_id,
            quantity_reserved=qi.quantity.quantize(Decimal("0.001")),
            status=status,
        )
        db.add(res)
        reservations.append(res)

    await db.flush()
    return reservations


async def release_reservations(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    quote_id: UUID | None = None,
    work_order_id: UUID | None = None,
) -> int:
    """Liberta reservas ativas associadas a um orçamento rejeitado ou OS cancelada."""
    conds = [PartReservation.tenant_id == tenant_id, PartReservation.status.in_(("active", "active_backorder"))]
    if quote_id:
        conds.append(PartReservation.quote_id == quote_id)
    if work_order_id:
        conds.append(PartReservation.work_order_id == work_order_id)

    res = await db.execute(select(PartReservation).where(*conds))
    active_rows = list(res.scalars().all())
    count = len(active_rows)

    for r in active_rows:
        r.status = "released"

    await db.flush()
    return count


async def issue_parts_for_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    inventory_id: UUID,
    quantity_requested: Decimal,
    *,
    actor_id: UUID | None = None,
    notes: str | None = None,
) -> dict:
    """Entrega de peças/óleos pelo fiel de armazém com verificação estrita de aprovação.

    Regras de Ouro:
      1. Lock FOR UPDATE no item de inventário.
      2. Agrega TODAS as reservas ativas para (work_order_id, inventory_id).
      3. Valida: se quantity_requested > total_approved_ceiling, BLOQUEIA com HTTP 409
         (exige Orçamento Suplementar com foto antes de qualquer consumo acima do aprovado).
      4. Consome as reservas por ordem FIFO determinística (created_at ASC, id ASC).
      5. Se a quantidade entregue for MENOR que o reservado (ex: 7.5L de 8.0L), LIBERTA a sobra
         automaticamente para o available_stock.
      6. Deduz atomicamente de current_quantity e grava SparePartMovement + MaintenancePartUsed.
    """
    quantity_requested = Decimal(str(quantity_requested)).quantize(Decimal("0.001"))
    if quantity_requested <= 0:
        raise ApiError("invalid_quantity", "Requested quantity must be positive.", status_code=400)

    # 1. Validar OS
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    if wo.status in ("closed", "cancelled"):
        raise ApiError("work_order_not_active", f"Work order is in status '{wo.status}'.", status_code=409)

    # 2. Lock FOR UPDATE no item de inventário
    inv = await db.scalar(
        select(SparePartInventory)
        .where(
            SparePartInventory.id == inventory_id,
            SparePartInventory.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if not inv:
        raise ApiError("part_not_found", "Spare part inventory item not found.", status_code=404)

    if inv.current_quantity < quantity_requested:
        raise ApiError(
            "insufficient_stock",
            f"Physical stock insufficient ({inv.current_quantity} {inv.unit} available, {quantity_requested} requested).",
            status_code=409,
        )

    # 3. Somatório de reservas aprovadas para este (work_order_id, inventory_id)
    active_res_query = await db.execute(
        select(PartReservation)
        .where(
            PartReservation.tenant_id == tenant_id,
            PartReservation.work_order_id == work_order_id,
            PartReservation.inventory_id == inventory_id,
            PartReservation.status.in_(("active", "active_backorder")),
        )
        .order_by(PartReservation.created_at.asc(), PartReservation.id.asc())
    )
    active_reservations = list(active_res_query.scalars().all())

    total_approved_ceiling = sum(r.quantity_reserved for r in active_reservations)

    # BLOQUEIO DE SEGURANÇA COMERCIAL (#1): Consumo acima do aprovado exige Orçamento Suplementar
    if quantity_requested > total_approved_ceiling:
        raise ApiError(
            "quantity_exceeds_approved_reservation",
            f"Quantidade solicitada ({quantity_requested} {inv.unit}) excede o tecto aprovado "
            f"pelo cliente ({total_approved_ceiling} {inv.unit}). Requer Orçamento Suplementar aprovado.",
            status_code=409,
            details={
                "approved_ceiling": str(total_approved_ceiling),
                "requested_quantity": str(quantity_requested),
            },
        )

    # 4. Consumir reservas FIFO determinístico e libertar sobras
    remaining_to_consume = quantity_requested
    for res in active_reservations:
        if remaining_to_consume <= 0:
            # Qualquer reserva restante inteira não utilizada é libertada
            res.status = "released"
            continue

        if res.quantity_reserved <= remaining_to_consume:
            # Consome totalmente esta reserva
            remaining_to_consume -= res.quantity_reserved
            res.status = "consumed"
        else:
            # Consumo parcial desta reserva (ex: 7.5L de 8.0L)
            surplus = res.quantity_reserved - remaining_to_consume
            res.quantity_reserved = remaining_to_consume
            res.status = "consumed"
            remaining_to_consume = Decimal("0")

            # Cria registo de libertação da sobra (0.500L)
            surplus_res = PartReservation(
                tenant_id=tenant_id,
                inventory_id=inventory_id,
                quote_id=res.quote_id,
                work_order_id=work_order_id,
                quantity_reserved=surplus,
                status="released",
            )
            db.add(surplus_res)

    # 5. Atualizar stock físico
    inv.current_quantity = (inv.current_quantity - quantity_requested).quantize(Decimal("0.001"))
    now = datetime.now(UTC)

    # 6. Gravar SparePartMovement (saída)
    unit_cost = inv.average_unit_cost
    total_cost = (quantity_requested * unit_cost).quantize(Decimal("0.01"))
    req_ref = f"ISSUE-WO-{wo.id.hex[:8]}-{now.strftime('%H%M%S')}"

    movement = SparePartMovement(
        tenant_id=tenant_id,
        inventory_id=inventory_id,
        movement_type="consumption",
        direction="out",
        quantity=quantity_requested,
        balance_after_quantity=inv.current_quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        request_reference=req_ref,
        source_type="work_order",
        source_id=work_order_id,
        occurred_at=now,
        recorded_by=actor_id,
        notes=notes or f"Entrega para OS {wo.work_order_number}",
    )
    db.add(movement)
    await db.flush()

    # 7. Gravar MaintenancePartUsed na OS
    part_used = MaintenancePartUsed(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        inventory_id=inventory_id,
        movement_id=movement.id,
        request_reference=req_ref,
        quantity=quantity_requested,
        unit_cost=unit_cost,
        total_cost=total_cost,
        issued_by=actor_id,
        issued_at=now,
        notes=notes,
    )
    db.add(part_used)

    # Audit log
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_inventory.parts_issued",
        entity_type="spare_part_movement",
        entity_id=movement.id,
        new_values={
            "work_order_id": str(work_order_id),
            "quantity": str(quantity_requested),
            "unit_cost": str(unit_cost),
            "total_cost": str(total_cost),
            "balance_after": str(inv.current_quantity),
        },
    )

    await db.commit()
    await db.refresh(inv)
    return {
        "movement_id": movement.id,
        "part_used_id": part_used.id,
        "inventory_id": inventory_id,
        "quantity_issued": float(quantity_requested),
        "current_stock": float(inv.current_quantity),
        "unit_cost": float(unit_cost),
        "total_cost": float(total_cost),
    }


async def return_part_from_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    inventory_id: UUID,
    quantity_to_return: Decimal,
    *,
    reason: str,
    actor_id: UUID | None = None,
) -> dict:
    """Devolução de sobra de peça/fluido da OS de volta para o armazém.

    Guarda de Imutabilidade: estritamente bloqueado se a OS já estiver 'closed' ou facturada (HTTP 409).
    Entrada gravada a Custo Médio WACC atual.
    """
    quantity_to_return = Decimal(str(quantity_to_return)).quantize(Decimal("0.001"))
    if quantity_to_return <= 0:
        raise ApiError("invalid_quantity", "Return quantity must be positive.", status_code=400)

    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    # GUARDA DE IMUTABILIDADE (#3): Não permite devolução se a OS já foi fechada/facturada
    if wo.status in ("closed", "cancelled"):
        raise ApiError(
            "work_order_already_billed",
            f"Cannot return parts for a work order in status '{wo.status}'. Retifications must be handled via fiscal credit notes.",
            status_code=409,
        )

    # Verificar se já existe fatura emitida para a OS
    existing_billed = await db.scalar(
        select(BillingDocument.id).where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.document_source == "workshop",
            BillingDocument.status.in_(("issued", "paid")),
            BillingDocument.contract_reference == wo.work_order_number,
        ).limit(1)
    )
    if existing_billed:
        raise ApiError(
            "work_order_already_billed",
            "Cannot return parts for an issued/paid invoice. Retifications must be handled via fiscal credit notes.",
            status_code=409,
        )

    # Lock FOR UPDATE on inventory item
    inv = await db.scalar(
        select(SparePartInventory)
        .where(
            SparePartInventory.id == inventory_id,
            SparePartInventory.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if not inv:
        raise ApiError("part_not_found", "Spare part inventory item not found.", status_code=404)

    now = datetime.now(UTC)
    inv.current_quantity = (inv.current_quantity + quantity_to_return).quantize(Decimal("0.001"))
    unit_cost = inv.average_unit_cost
    total_cost = (quantity_to_return * unit_cost).quantize(Decimal("0.01"))
    req_ref = f"RETURN-WO-{wo.id.hex[:8]}-{now.strftime('%H%M%S')}"

    movement = SparePartMovement(
        tenant_id=tenant_id,
        inventory_id=inventory_id,
        movement_type="return",
        direction="in",
        quantity=quantity_to_return,
        balance_after_quantity=inv.current_quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        request_reference=req_ref,
        source_type="work_order",
        source_id=work_order_id,
        occurred_at=now,
        recorded_by=actor_id,
        notes=f"Devolução da OS {wo.work_order_number}: {reason}",
    )
    db.add(movement)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_inventory.part_returned",
        entity_type="spare_part_movement",
        entity_id=movement.id,
        new_values={
            "work_order_id": str(work_order_id),
            "quantity_returned": str(quantity_to_return),
            "reason": reason,
            "balance_after": str(inv.current_quantity),
        },
    )

    await db.commit()
    await db.refresh(inv)
    return {
        "movement_id": movement.id,
        "quantity_returned": float(quantity_to_return),
        "current_stock": float(inv.current_quantity),
    }


async def cancel_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    *,
    reason: str,
    actor_id: UUID | None = None,
) -> dict:
    """Cancela uma Ordem de Serviço, liberta reservas órfãs e anula fatura em draft (se existir)."""
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    if wo.status in ("closed", "cancelled"):
        raise ApiError("invalid_work_order_status", f"Work order is already '{wo.status}'.", status_code=409)

    wo.status = "cancelled"
    wo.close_notes = f"Cancelada: {reason}"

    # 1. Libertação de Reservas Órfãs (#5)
    released_count = await release_reservations(db, tenant_id, work_order_id=work_order_id)

    # 2. Anulação de Fatura em Draft associada (#3 das notas finas)
    draft_docs_res = await db.execute(
        select(BillingDocument).where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.document_source == "workshop",
            BillingDocument.status == "draft",
            BillingDocument.contract_reference == wo.work_order_number,
        )
    )
    cancelled_drafts = 0
    for doc in draft_docs_res.scalars().all():
        doc.status = "cancelled"
        doc.cancellation_reason = f"OS {wo.work_order_number} cancelada: {reason}"
        cancelled_drafts += 1

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order.cancelled",
        entity_type="work_order",
        entity_id=wo.id,
        new_values={
            "reason": reason,
            "released_reservations": released_count,
            "cancelled_drafts": cancelled_drafts,
        },
    )

    await db.commit()
    await db.refresh(wo)
    return {
        "work_order_id": wo.id,
        "status": "cancelled",
        "released_reservations": released_count,
        "cancelled_drafts": cancelled_drafts,
    }


async def record_inventory_adjustment(
    db: AsyncSession,
    tenant_id: UUID,
    inventory_id: UUID,
    quantity_adjusted: Decimal,
    direction: str,  # "in" | "out"
    reason: str,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Ajuste de Inventário / Perda Residual (requer permissão WORKSHOP_INVENTORY_ADJUST)."""
    if not reason or not reason.strip():
        raise ApiError("reason_required", "Adjustment reason is mandatory.", status_code=422)

    quantity_adjusted = Decimal(str(quantity_adjusted)).quantize(Decimal("0.001"))
    if quantity_adjusted <= 0:
        raise ApiError("invalid_quantity", "Quantity must be positive.", status_code=400)

    inv = await db.scalar(
        select(SparePartInventory)
        .where(
            SparePartInventory.id == inventory_id,
            SparePartInventory.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if not inv:
        raise ApiError("part_not_found", "Spare part inventory item not found.", status_code=404)

    if direction == "out" and inv.current_quantity < quantity_adjusted:
        raise ApiError("insufficient_stock", "Stock level too low for adjustment.", status_code=409)

    if direction == "in":
        inv.current_quantity = (inv.current_quantity + quantity_adjusted).quantize(Decimal("0.001"))
    else:
        inv.current_quantity = (inv.current_quantity - quantity_adjusted).quantize(Decimal("0.001"))

    now = datetime.now(UTC)
    unit_cost = inv.average_unit_cost
    total_cost = (quantity_adjusted * unit_cost).quantize(Decimal("0.01"))
    req_ref = f"ADJ-{inv.id.hex[:8]}-{now.strftime('%H%M%S')}"

    movement = SparePartMovement(
        tenant_id=tenant_id,
        inventory_id=inventory_id,
        movement_type="adjustment",
        direction=direction,
        quantity=quantity_adjusted,
        balance_after_quantity=inv.current_quantity,
        unit_cost=unit_cost,
        total_cost=total_cost,
        request_reference=req_ref,
        source_type="inventory_adjustment",
        occurred_at=now,
        recorded_by=actor_id,
        notes=f"Ajuste de Stock ({direction.upper()}): {reason}",
    )
    db.add(movement)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_inventory.adjustment",
        entity_type="spare_part_movement",
        entity_id=movement.id,
        new_values={
            "direction": direction,
            "quantity": str(quantity_adjusted),
            "reason": reason,
            "balance_after": str(inv.current_quantity),
        },
    )

    await db.commit()
    await db.refresh(inv)
    return {
        "movement_id": movement.id,
        "direction": direction,
        "quantity": float(quantity_adjusted),
        "current_stock": float(inv.current_quantity),
    }


async def get_reorder_suggestions(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[dict]:
    """Lista de peças que atingiram o limite mínimo considerando stock disponível."""
    parts_res = await db.execute(
        select(SparePartInventory).where(
            SparePartInventory.tenant_id == tenant_id,
            SparePartInventory.status == "active",
        )
    )
    parts = list(parts_res.scalars().all())
    suggestions = []

    for item in parts:
        avail = await get_available_stock(db, tenant_id, item.id)
        if avail <= item.minimum_quantity:
            # Buscar orçamentos bloqueados por faltas
            backorders_res = await db.execute(
                select(PartReservation).where(
                    PartReservation.tenant_id == tenant_id,
                    PartReservation.inventory_id == item.id,
                    PartReservation.status == "active_backorder",
                )
            )
            backorder_rows = list(backorders_res.scalars().all())

            suggestions.append({
                "inventory_id": item.id,
                "sku": item.sku,
                "name": item.name,
                "unit": item.unit,
                "current_quantity": float(item.current_quantity),
                "available_stock": float(avail),
                "minimum_quantity": float(item.minimum_quantity),
                "reorder_quantity": item.reorder_quantity or 10,
                "lead_time_days": item.lead_time_days,
                "supplier_name": item.supplier_name,
                "backorders_count": len(backorder_rows),
                "blocked_work_order_ids": [str(b.work_order_id) for b in backorder_rows if b.work_order_id],
            })

    return suggestions


async def get_inventory_valuation_summary(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict:
    """Balancete de valorização de stock total e por categoria."""
    parts_res = await db.execute(
        select(SparePartInventory).where(
            SparePartInventory.tenant_id == tenant_id,
            SparePartInventory.status == "active",
        )
    )
    parts = list(parts_res.scalars().all())

    total_value = Decimal("0")
    categories: dict[str, dict] = {}

    for p in parts:
        item_val = (p.current_quantity * p.average_unit_cost).quantize(Decimal("0.01"))
        total_value += item_val

        cat = p.category or "Geral"
        if cat not in categories:
            categories[cat] = {"category": cat, "items_count": 0, "total_value": Decimal("0")}
        categories[cat]["items_count"] += 1
        categories[cat]["total_value"] += item_val

    return {
        "total_items_count": len(parts),
        "total_valuation_mzn": float(total_value),
        "categories": [
            {
                "category": c["category"],
                "items_count": c["items_count"],
                "total_value": float(c["total_value"]),
            }
            for c in categories.values()
        ],
    }


# --- Purchase Orders & Core Return Workflows ---


async def create_purchase_order(
    db: AsyncSession,
    tenant_id: UUID,
    supplier_third_party_id: UUID,
    items_data: list[dict],  # [{"inventory_id": UUID, "quantity_ordered": Decimal, "unit_price": Decimal}]
    *,
    supplier_invoice_number: str | None = None,
    notes: str | None = None,
    actor_id: UUID | None = None,
) -> WorkshopPurchaseOrder:
    """Criar nova Encomenda de Compra a Fornecedor Terceiro (ThirdParty)."""
    supplier = await db.get(ThirdParty, supplier_third_party_id)
    if not supplier or supplier.tenant_id != tenant_id:
        raise ApiError("supplier_not_found", "Supplier third party not found.", status_code=404)

    now = datetime.now(UTC)
    po_number = f"PO-2026-{now.strftime('%m%d%H%M%S')}"

    total_po_amount = Decimal("0")
    po_items: list[WorkshopPurchaseOrderItem] = []

    po = WorkshopPurchaseOrder(
        tenant_id=tenant_id,
        supplier_third_party_id=supplier_third_party_id,
        po_number=po_number,
        status="ordered",
        supplier_invoice_number=supplier_invoice_number,
        notes=notes,
        created_by=actor_id,
    )
    db.add(po)
    await db.flush()

    for item in items_data:
        inv_id = item["inventory_id"]
        qty = Decimal(str(item["quantity_ordered"])).quantize(Decimal("0.001"))
        price = Decimal(str(item["unit_price"])).quantize(Decimal("0.02"))
        item_total = (qty * price).quantize(Decimal("0.02"))

        po_item = WorkshopPurchaseOrderItem(
            tenant_id=tenant_id,
            purchase_order_id=po.id,
            inventory_id=inv_id,
            quantity_ordered=qty,
            quantity_received=Decimal("0"),
            unit_price=price,
            total_price=item_total,
        )
        db.add(po_item)
        po_items.append(po_item)
        total_po_amount += item_total

    po.total_amount = total_po_amount
    await db.commit()
    await db.refresh(po)
    return po


async def receive_purchase_order(
    db: AsyncSession,
    tenant_id: UUID,
    purchase_order_id: UUID,
    *,
    supplier_invoice_number: str | None = None,
    actor_id: UUID | None = None,
) -> dict:
    """Recepção física de mercadoria da Encomenda de Compra com recálculo WACC."""
    po = await db.get(WorkshopPurchaseOrder, purchase_order_id)
    if not po or po.tenant_id != tenant_id:
        raise ApiError("po_not_found", "Purchase order not found.", status_code=404)

    if po.status in ("received", "cancelled"):
        raise ApiError("invalid_po_status", f"Purchase order is already '{po.status}'.", status_code=409)

    items_res = await db.execute(
        select(WorkshopPurchaseOrderItem).where(
            WorkshopPurchaseOrderItem.purchase_order_id == po.id,
            WorkshopPurchaseOrderItem.tenant_id == tenant_id,
        )
    )
    po_items = list(items_res.scalars().all())
    now = datetime.now(UTC)

    for item in po_items:
        qty_to_receive = item.quantity_ordered - item.quantity_received
        if qty_to_receive <= 0:
            continue

        # Lock FOR UPDATE on inventory item
        inv = await db.scalar(
            select(SparePartInventory)
            .where(
                SparePartInventory.id == item.inventory_id,
                SparePartInventory.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if not inv:
            continue

        # Recálculo do Custo Médio Ponderado (WACC)
        old_stock = inv.current_quantity
        old_cost = inv.average_unit_cost
        new_cost = item.unit_price

        if (old_stock + qty_to_receive) > 0:
            wacc = ((old_stock * old_cost) + (qty_to_receive * new_cost)) / (old_stock + qty_to_receive)
            inv.average_unit_cost = Decimal(str(wacc)).quantize(Decimal("0.02"))

        inv.current_quantity = (inv.current_quantity + qty_to_receive).quantize(Decimal("0.001"))
        item.quantity_received = item.quantity_ordered

        # Gravar movimento de entrada (receipt)
        movement = SparePartMovement(
            tenant_id=tenant_id,
            inventory_id=inv.id,
            movement_type="receipt",
            direction="in",
            quantity=qty_to_receive,
            balance_after_quantity=inv.current_quantity,
            unit_cost=new_cost,
            total_cost=(qty_to_receive * new_cost).quantize(Decimal("0.02")),
            request_reference=f"PO-REC-{po.po_number}",
            source_type="purchase_order",
            source_id=po.id,
            occurred_at=now,
            recorded_by=actor_id,
            notes=f"Recepção da PO {po.po_number}",
        )
        db.add(movement)

    po.status = "received"
    if supplier_invoice_number:
        po.supplier_invoice_number = supplier_invoice_number

    await db.commit()
    await db.refresh(po)
    return {
        "purchase_order_id": po.id,
        "po_number": po.po_number,
        "status": po.status,
        "total_amount": float(po.total_amount),
    }


async def register_core_return(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    inventory_id: UUID,
    description: str,
    *,
    serial_number: str | None = None,
    evidence_photo_file_id: UUID | None = None,
    supplier_third_party_id: UUID | None = None,
    actor_id: UUID | None = None,
) -> CoreReturnItem:
    """Registar peça velha substituída (Core Return) com foto de evidência."""
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    core_item = CoreReturnItem(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        inventory_id=inventory_id,
        description=description,
        serial_number=serial_number,
        evidence_photo_file_id=evidence_photo_file_id,
        supplier_third_party_id=supplier_third_party_id,
        status="pending_return",
    )
    db.add(core_item)
    await db.commit()
    await db.refresh(core_item)
    return core_item


async def credit_core_return(
    db: AsyncSession,
    tenant_id: UUID,
    core_return_id: UUID,
    credit_amount: Decimal,
    *,
    actor_id: UUID | None = None,
) -> CoreReturnItem:
    """Dar baixa da peça velha com confirmação do valor de crédito concedido pelo fornecedor."""
    core = await db.get(CoreReturnItem, core_return_id)
    if not core or core.tenant_id != tenant_id:
        raise ApiError("core_return_not_found", "Core return item not found.", status_code=404)

    core.credit_amount = Decimal(str(credit_amount)).quantize(Decimal("0.02"))
    core.status = "credited"
    await db.commit()
    await db.refresh(core)
    return core
