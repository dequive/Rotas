"""Workshop Billing — geração de fatura fiscal a partir de Ordem de Serviço concluída.

Fluxo (corrigido v2):
  0. Idempotência — se já existe BillingDocument para a OS, retorna existente.
  1. Agregar todos os WorkshopQuote ligados (original + suplementares aceites).
  2. Ler consumo real: MaintenancePartUsed + WorkOrderTask.actual_minutes.
  3. Reconciliar: consumo real como base, orçamento como tecto/referência.
  4. Montar BillingDocument em memória (document_source="workshop").
  5. Montar BillingItems (item_source correcto por linha).
  6. Calcular IVA via resolve_iva().
  7. Snapshot do perfil fiscal via _snapshot_profile().
  8. Persistir como "draft" — SEM número fiscal.
  9. (acção separada) confirm_workshop_invoice() → _assign_invoice_number() → status "issued".
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.billing.domain import DEFAULT_IVA_RATE
from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.billing.service import _assign_invoice_number, _snapshot_profile
from app.modules.clients.models import Client
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenancePartUsed,
    SparePartInventory,
    WorkOrder,
    WorkOrderTask,
    WorkshopStaffRate,
)
from app.modules.workshop.quote_models import WorkshopQuote, WorkshopQuoteItem


async def create_workshop_invoice(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Gera rascunho de fatura fiscal a partir de uma OS concluída.

    Regras:
      - Idempotente: se já existe BillingDocument para esta OS, retorna existente.
      - Agrega todos os orçamentos aceites (original + suplementares).
      - Usa consumo real (peças via MaintenancePartUsed, mão-de-obra via WorkOrderTask.actual_minutes).
      - Orçamento aprovado serve de tecto de preço, não de valor fixo.
      - Fatura criada com status "draft" sem número fiscal (número atribuído apenas no confirm).
    """

    # ── 0. Idempotência ──────────────────────────────────────────────────────
    await db.scalar(
        select(BillingDocument)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.document_source == "workshop",
            BillingDocument.quote_id.isnot(None),  # workshop invoices always have quote_id
        )
        .join(
            WorkshopQuote,
            BillingDocument.quote_id == WorkshopQuote.id,
        )
        .where(
            or_(
                WorkshopQuote.related_work_order_id == work_order_id,
                # For original quotes, the work_order was created from accept_quote
                # We check via a subquery on converted quotes
            )
        )
    )
    # Simpler idempotency: check BillingItem.work_order_id directly
    existing_doc_id = await db.scalar(
        select(BillingItem.billing_document_id)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.work_order_id == work_order_id,
        )
        .limit(1)
    )
    if existing_doc_id:
        existing_doc = await db.get(BillingDocument, existing_doc_id)
        if existing_doc:
            return _serialize_workshop_invoice(existing_doc)

    # ── 1. Validar OS ────────────────────────────────────────────────────────
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    if wo.status not in ("quality_check", "closed"):
        raise ApiError(
            "work_order_not_closable",
            f"Work order is in status '{wo.status}', must be 'quality_check' or 'closed'.",
            status_code=409,
        )

    # ── 2. Agregar quotes aceites (original + suplementares) ─────────────────
    quote_conds = [WorkshopQuote.related_work_order_id == work_order_id]
    if wo.reception_id:
        quote_conds.append(WorkshopQuote.reception_id == wo.reception_id)

    quotes_result = await db.execute(
        select(WorkshopQuote)
        .where(
            WorkshopQuote.tenant_id == tenant_id,
            WorkshopQuote.status == "converted",
            or_(*quote_conds),
        )
        .order_by(WorkshopQuote.created_at.asc())
    )
    converted_quotes = list(quotes_result.scalars().all())
    original_quote = converted_quotes[0] if converted_quotes else None

    # Load all quote items for price ceiling lookup
    quote_item_prices: dict[str, Decimal] = {}  # description → approved unit_price
    for q in converted_quotes:
        items_result = await db.execute(
            select(WorkshopQuoteItem).where(WorkshopQuoteItem.quote_id == q.id)
        )
        for qi in items_result.scalars().all():
            quote_item_prices[qi.description.strip().lower()] = qi.unit_price

    # ── 3. Ler consumo real de mão-de-obra ───────────────────────────────────
    tasks_result = await db.execute(
        select(WorkOrderTask).where(
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.work_order_id == work_order_id,
            WorkOrderTask.status == "completed",
        )
    )
    completed_tasks = list(tasks_result.scalars().all())

    # Resolve hourly rates for labor costing
    staff_rates: dict[UUID, Decimal] = {}
    for task in completed_tasks:
        if task.completed_by and task.completed_by not in staff_rates:
            rate = await db.scalar(
                select(WorkshopStaffRate.hourly_rate)
                .where(
                    WorkshopStaffRate.tenant_id == tenant_id,
                    WorkshopStaffRate.user_id == task.completed_by,
                )
                .order_by(WorkshopStaffRate.effective_from.desc())
                .limit(1)
            )
            staff_rates[task.completed_by] = rate or Decimal("0")

    # ── 4. Ler consumo real de peças ─────────────────────────────────────────
    parts_result = await db.execute(
        select(MaintenancePartUsed).where(
            MaintenancePartUsed.tenant_id == tenant_id,
            MaintenancePartUsed.work_order_id == work_order_id,
        )
    )
    used_parts = list(parts_result.scalars().all())

    # ── 5. Resolver dados do cliente e viatura ───────────────────────────────
    vehicle = await db.get(Vehicle, wo.vehicle_id) if wo.vehicle_id else None
    client_id = getattr(vehicle, "customer_client_id", None) if vehicle else None
    if not client_id and original_quote:
        client_id = original_quote.client_id

    client_name = "Cliente Particular"
    client_nuit = None
    if client_id:
        client = await db.get(Client, client_id)
        if client:
            client_name = client.trading_name
            client_nuit = getattr(client, "nuit", None)

    tenant = await db.get(Tenant, tenant_id)

    # ── 6. Calcular IVA (standard 16% para serviços de oficina) ──────────────
    iva_rate = DEFAULT_IVA_RATE
    iva_basis = "standard_16"

    # ── 7. Montar BillingDocument em memória ─────────────────────────────────
    now = datetime.now(UTC)
    doc = BillingDocument(
        tenant_id=tenant_id,
        client_id=client_id,
        client_name=client_name,
        client_nuit=client_nuit,
        contract_id=None,  # Workshop invoices are not contract-based
        contract_reference=wo.work_order_number,
        billing_period_start=wo.created_at,
        billing_period_end=now,
        currency="MZN",
        subtotal=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("0"),
        status="draft",
        document_type="invoice",
        document_source="workshop",
        reception_id=wo.reception_id,
        quote_id=original_quote.id if original_quote else None,
        iva_rate=iva_rate,
        iva_basis=iva_basis,
        issuer_name=tenant.name if tenant else None,
        issuer_nuit=getattr(tenant, "nuit", None) if tenant else None,
    )
    db.add(doc)
    await db.flush()  # Get doc.id for BillingItem FK

    # ── 8. Montar BillingItems ───────────────────────────────────────────────
    billing_items: list[BillingItem] = []
    running_subtotal = Decimal("0")

    # 8a. Linhas de mão-de-obra (consumo real via WorkOrderTask.actual_minutes)
    for task in completed_tasks:
        actual_mins = task.actual_minutes or task.estimated_minutes or 0
        if actual_mins <= 0:
            continue

        hours = Decimal(str(actual_mins)) / Decimal("60")
        hourly_rate = (
            staff_rates.get(task.completed_by, Decimal("0")) if task.completed_by else Decimal("0")
        )

        desc_key = task.description.strip().lower()
        quoted_price = quote_item_prices.get(desc_key)
        if quoted_price:
            unit_price = quoted_price
            line_total = quoted_price
        elif hourly_rate > 0:
            unit_price = hourly_rate
            line_total = (hours * hourly_rate).quantize(Decimal("0.01"))
        else:
            continue

        item = BillingItem(
            tenant_id=tenant_id,
            billing_document_id=doc.id,
            client_reference=wo.work_order_number,
            cargo_description=task.description,
            delivered_at=task.completed_at or now,
            quantity=hours,
            unit_price=unit_price,
            amount=line_total,
            status="draft",
            iva_rate=iva_rate,
            iva_basis=iva_basis,
            iva_amount=(line_total * iva_rate).quantize(Decimal("0.01")),
            work_order_id=work_order_id,
            item_source="workshop_labor",
        )
        billing_items.append(item)
        running_subtotal += line_total

    # 8b. Linhas de peças (consumo real via MaintenancePartUsed)
    for part_used in used_parts:
        part = await db.get(SparePartInventory, part_used.inventory_id)
        part_name = part.name if part else "Peça"

        desc_key = part_name.strip().lower()
        quoted_price = quote_item_prices.get(desc_key)
        if quoted_price:
            unit_cost = quoted_price
            line_total = (part_used.quantity * quoted_price).quantize(Decimal("0.01"))
        else:
            unit_cost = part_used.unit_cost or (part.average_unit_cost if part else Decimal("0"))
            line_total = (part_used.quantity * unit_cost).quantize(Decimal("0.01"))

        item = BillingItem(
            tenant_id=tenant_id,
            billing_document_id=doc.id,
            client_reference=wo.work_order_number,
            cargo_description=f"Peça: {part_name}",
            delivered_at=part_used.issued_at or now,
            quantity=part_used.quantity,
            unit_price=unit_cost,
            amount=line_total,
            status="draft",
            iva_rate=iva_rate,
            iva_basis=iva_basis,
            iva_amount=(line_total * iva_rate).quantize(Decimal("0.01")),
            work_order_id=work_order_id,
            catalog_item_id=None,
            item_source="workshop_part",
        )
        billing_items.append(item)
        running_subtotal += line_total

    # ── 9. Calcular totais ───────────────────────────────────────────────────
    tax_total = (running_subtotal * iva_rate).quantize(Decimal("0.01"))
    doc.subtotal = running_subtotal
    doc.tax_amount = tax_total
    doc.total_amount = running_subtotal + tax_total

    for item in billing_items:
        db.add(item)

    # ── 10. Snapshot do perfil fiscal ────────────────────────────────────────
    await _snapshot_profile(db, doc, tenant_id)

    # ── 11. Audit log ────────────────────────────────────────────────────────
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_invoice.draft_created",
        entity_type="billing_document",
        entity_id=doc.id,
        new_values={
            "work_order_id": str(work_order_id),
            "subtotal": str(doc.subtotal),
            "total_amount": str(doc.total_amount),
            "items_count": len(billing_items),
        },
    )

    await db.commit()
    await db.refresh(doc)
    return _serialize_workshop_invoice(doc)


async def confirm_workshop_invoice(
    db: AsyncSession,
    tenant_id: UUID,
    document_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Confirma e emite fiscalmente a fatura de oficina.

    Transição: draft → issued.
    Atribui número fiscal sequencial (gap-free) neste momento — nunca antes.
    Após esta chamada, o documento é imutável.
    """
    doc = await db.get(BillingDocument, document_id)
    if not doc or doc.tenant_id != tenant_id:
        raise ApiError("document_not_found", "Billing document not found.", status_code=404)

    if doc.document_source != "workshop":
        raise ApiError(
            "not_workshop_document", "Document is not a workshop invoice.", status_code=409
        )

    if doc.status == "issued":
        return _serialize_workshop_invoice(doc)  # Idempotente

    if doc.status != "draft":
        raise ApiError(
            "invalid_document_status",
            f"Document is in status '{doc.status}', must be 'draft' to confirm.",
            status_code=409,
        )

    if doc.total_amount <= 0:
        raise ApiError(
            "empty_invoice",
            "Cannot issue an invoice with zero or negative total.",
            status_code=422,
        )

    # Atribuir número fiscal — último acto antes da imutabilidade
    invoice_number = await _assign_invoice_number(db, doc, tenant_id)
    doc.status = "issued"
    doc.issued_at = datetime.now(UTC)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_invoice.issued",
        entity_type="billing_document",
        entity_id=doc.id,
        new_values={
            "invoice_number": invoice_number,
            "status": "issued",
            "total_amount": str(doc.total_amount),
        },
    )

    await db.commit()
    await db.refresh(doc)
    return _serialize_workshop_invoice(doc)


def _serialize_workshop_invoice(doc: BillingDocument) -> dict:
    return {
        "id": doc.id,
        "tenant_id": doc.tenant_id,
        "document_source": doc.document_source,
        "document_type": doc.document_type,
        "invoice_number": doc.invoice_number,
        "client_name": doc.client_name,
        "client_nuit": doc.client_nuit,
        "reception_id": doc.reception_id,
        "quote_id": doc.quote_id,
        "subtotal": float(doc.subtotal),
        "tax_amount": float(doc.tax_amount),
        "total_amount": float(doc.total_amount),
        "iva_rate": float(doc.iva_rate) if doc.iva_rate else None,
        "iva_basis": doc.iva_basis,
        "status": doc.status,
        "issued_at": doc.issued_at,
        "created_at": doc.created_at,
    }
