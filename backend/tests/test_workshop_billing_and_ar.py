import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from app.core.errors import ApiError
from app.modules.billing.models import BillingDocument, ClientPayment, PaymentAllocation
from app.modules.billing.schemas import ClientPaymentCreate
from app.modules.billing.service import (
    get_client_statement,
    register_payment,
    void_payment,
)
from app.modules.clients.models import Client
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenancePartUsed,
    SparePartInventory,
    WorkOrder,
    WorkOrderTask,
)
from app.modules.workshop.quote_models import WorkshopQuote, WorkshopQuoteItem
from app.modules.workshop.quote_service import accept_quote
from app.modules.workshop.service import close_work_order
from app.modules.workshop.schemas import WorkOrderCloseRequest
from app.modules.workshop.workshop_billing_service import (
    confirm_workshop_invoice,
    create_workshop_invoice,
)


@pytest.mark.asyncio
async def test_workshop_invoice_multi_quote_idempotency_and_confirmation(db, tenant_id):
    # 1. Create client & vehicle
    client = Client(tenant_id=tenant_id, trading_name="Cliente Teste Lda", nuit="123456789")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate="MM-99-ZZ",
        brand="Toyota",
        model="Hilux",
        customer_client_id=client.id,
    )
    db.add(vehicle)
    await db.flush()

    # 2. Create original quote
    quote_orig = WorkshopQuote(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        client_id=client.id,
        quote_number="ORC-2026-0001",
        status="sent",
        labor_total=Decimal("5000.00"),
        parts_total=Decimal("2000.00"),
        total_amount=Decimal("7000.00"),
    )
    db.add(quote_orig)
    await db.flush()

    item1 = WorkshopQuoteItem(
        tenant_id=tenant_id,
        quote_id=quote_orig.id,
        item_type="labor",
        description="Mão de Obra Diagnóstico",
        unit_price=Decimal("5000.00"),
        total_price=Decimal("5000.00"),
    )
    item2 = WorkshopQuoteItem(
        tenant_id=tenant_id,
        quote_id=quote_orig.id,
        item_type="part",
        description="Filtro de Óleo",
        quantity=Decimal("1"),
        unit_price=Decimal("2000.00"),
        total_price=Decimal("2000.00"),
    )
    db.add_all([item1, item2])
    await db.flush()

    # Convert original quote -> creates WorkOrder
    accepted = await accept_quote(db, tenant_id, quote_orig.id)
    wo_id = accepted["work_order_id"]

    # 3. Create supplemental quote linked to same WorkOrder
    quote_supp = WorkshopQuote(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        client_id=client.id,
        quote_number="ORC-2026-0002",
        is_supplemental=True,
        related_work_order_id=wo_id,
        status="sent",
        labor_total=Decimal("1500.00"),
        total_amount=Decimal("1500.00"),
    )
    db.add(quote_supp)
    await db.flush()

    item_supp = WorkshopQuoteItem(
        tenant_id=tenant_id,
        quote_id=quote_supp.id,
        item_type="labor",
        description="Calibração Adicional",
        unit_price=Decimal("1500.00"),
        total_price=Decimal("1500.00"),
    )
    db.add(item_supp)
    await db.flush()

    await accept_quote(db, tenant_id, quote_supp.id)

    # 4. Set WorkOrder status to quality_check and close it
    wo = await db.get(WorkOrder, wo_id)
    wo.status = "quality_check"
    await db.flush()

    # Complete tasks so labor gets priced
    tasks_res = await db.execute(
        select(WorkOrderTask).where(WorkOrderTask.work_order_id == wo_id)
    )
    for t in tasks_res.scalars():
        t.status = "completed"
        t.actual_minutes = 60
    await db.flush()

    # Record part used
    part_inv = SparePartInventory(
        tenant_id=tenant_id,
        sku="SKU-FILT-01",
        name="Filtro de Óleo",
        average_unit_cost=Decimal("1800.00"),
    )
    db.add(part_inv)
    await db.flush()

    part_used = MaintenancePartUsed(
        tenant_id=tenant_id,
        work_order_id=wo_id,
        inventory_id=part_inv.id,
        request_reference="REF-001",
        quantity=Decimal("1"),
        unit_cost=Decimal("1800.00"),
        total_cost=Decimal("1800.00"),
    )
    db.add(part_used)
    await db.flush()

    # Close WO — should auto-generate draft invoice
    close_res = await close_work_order(
        db,
        tenant_id,
        wo_id,
        WorkOrderCloseRequest(actual_cost=Decimal("6800.00"), notes="Concluído com sucesso"),
        actor_id=None,
    )
    assert "workshop_invoice_draft" in close_res
    draft_invoice = close_res["workshop_invoice_draft"]
    assert draft_invoice["status"] == "draft"
    assert draft_invoice["invoice_number"] is None

    # Test Idempotency: calling create_workshop_invoice a 2nd time returns SAME draft without duplicate
    draft_2nd = await create_workshop_invoice(db, tenant_id, wo_id)
    assert draft_2nd["id"] == draft_invoice["id"]

    # Verify only ONE BillingDocument exists for this tenant & quote
    docs_cnt = await db.scalar(
        select(BillingDocument).where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.quote_id == quote_orig.id,
        )
    )
    assert docs_cnt is not None

    # 5. Confirm invoice (issues gap-free number and imutability)
    confirmed = await confirm_workshop_invoice(db, tenant_id, draft_invoice["id"])
    assert confirmed["status"] == "issued"
    assert confirmed["invoice_number"] is not None
    assert "2026/" in confirmed["invoice_number"]

    # 6. Verify statement AR reflects confirmed invoice
    stmt = await get_client_statement(db, tenant_id, client.id)
    assert stmt["total_invoiced"] == Decimal(str(confirmed["total_amount"]))
    assert stmt["balance"] == Decimal(str(confirmed["total_amount"]))


@pytest.mark.asyncio
async def test_payment_allocation_overpayment_guard_and_partial_voiding(db, tenant_id):
    client = Client(tenant_id=tenant_id, trading_name="Cliente AR Teste", nuit="987654321")
    db.add(client)
    await db.flush()

    doc = BillingDocument(
        tenant_id=tenant_id,
        client_id=client.id,
        client_name=client.trading_name,
        contract_reference="REF-TEST",
        billing_period_start=datetime.now(UTC),
        billing_period_end=datetime.now(UTC),
        subtotal=Decimal("10000.00"),
        tax_amount=Decimal("1600.00"),
        total_amount=Decimal("11600.00"),
        status="issued",
        document_type="invoice",
        document_source="workshop",
        invoice_number="2026/0005",
        issued_at=datetime.now(UTC),
    )
    db.add(doc)
    await db.flush()

    # 1. Overpayment guard: attempt to pay 15,000 MZN on 11,600 MZN invoice -> HTTP 409
    with pytest.raises(ApiError) as exc_info:
        await register_payment(
            db,
            tenant_id,
            user_id=None,
            payload=ClientPaymentCreate(
                client_id=client.id,
                billing_document_id=doc.id,
                amount=Decimal("15000.00"),
                payment_method="bank_transfer",
                value_date=datetime.now(UTC),
            ),
        )
    assert exc_info.value.code == "payment_exceeds_invoice_balance"

    # 2. Register Partial Payment 1: 6,000 MZN (approx 51.7%)
    pay1 = await register_payment(
        db,
        tenant_id,
        user_id=None,
        payload=ClientPaymentCreate(
            client_id=client.id,
            billing_document_id=doc.id,
            amount=Decimal("6000.00"),
            payment_method="bank_transfer",
            value_date=datetime.now(UTC),
        ),
    )
    await db.refresh(doc)
    assert doc.status == "issued"

    # 3. Register Partial Payment 2: 5,600 MZN (completes 11,600 MZN total)
    pay2 = await register_payment(
        db,
        tenant_id,
        user_id=None,
        payload=ClientPaymentCreate(
            client_id=client.id,
            billing_document_id=doc.id,
            amount=Decimal("5600.00"),
            payment_method="cheque",
            value_date=datetime.now(UTC),
        ),
    )
    await db.refresh(doc)
    assert doc.status == "paid"

    stmt_before_void = await get_client_statement(db, tenant_id, client.id)
    assert stmt_before_void["total_invoiced"] == Decimal("11600.00")
    assert stmt_before_void["total_paid"] == Decimal("11600.00")
    assert stmt_before_void["balance"] == Decimal("0.00")

    # 4. Void Payment 1 (6,000 MZN) only
    await void_payment(
        db,
        payment_id=pay1["id"],
        tenant_id=tenant_id,
        user_id=None,
        void_reason="Cheque sem cobertura",
    )

    # 5. Verify document status reverted from 'paid' back to 'issued' (NOT 0% paid, but 5,600 MZN paid)
    await db.refresh(doc)
    assert doc.status == "issued"

    stmt_after_void = await get_client_statement(db, tenant_id, client.id)
    assert stmt_after_void["total_invoiced"] == Decimal("11600.00")
    assert stmt_after_void["total_paid"] == Decimal("5600.00")  # Payment 2 remains confirmed
    assert stmt_after_void["balance"] == Decimal("6000.00")    # 6,000 MZN remaining balance
