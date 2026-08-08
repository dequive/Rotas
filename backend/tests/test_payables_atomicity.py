import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.modules.accounting.models import Account, JournalEntry
from app.modules.audit.models import AuditLog
from app.modules.payables.models import SupplierInvoice, SupplierPayment
from app.modules.sync.models import IdempotencyKey
from app.modules.third_party.models import ThirdParty


async def _seed_payable(db, tenant_id, *, include_bank_account: bool = True):
    supplier = ThirdParty(
        tenant_id=tenant_id,
        name=f"Fornecedor {uuid4().hex[:8]}",
        nuit=uuid4().hex[:9],
    )
    db.add(supplier)
    await db.flush()
    invoice = SupplierInvoice(
        tenant_id=tenant_id,
        third_party_id=supplier.id,
        invoice_number=f"FNF-{uuid4().hex[:8]}",
        amount=Decimal("1000.00"),
        currency="MZN",
        issued_at=datetime.now(UTC),
        status="pending",
    )
    accounts = [
        Account(tenant_id=tenant_id, code="42", name="Fornecedores", account_type="Liability")
    ]
    if include_bank_account:
        accounts.append(
            Account(tenant_id=tenant_id, code="12", name="Depósitos à ordem", account_type="Asset")
        )
    db.add_all([invoice, *accounts])
    await db.commit()
    return invoice


async def test_supplier_invoice_payment_is_atomic_and_idempotent(
    async_client, auth_headers, db, tenant_id
):
    invoice = await _seed_payable(db, tenant_id)
    key = f"supplier-payment:{uuid4()}"
    headers = {**auth_headers, "Idempotency-Key": key}
    payload = {
        "amount": "1000.00",
        "payment_method": "bank_transfer",
        "value_date": datetime.now(UTC).isoformat(),
        "reference": "TRF-ATOMIC-001",
    }
    url = f"/api/v1/payables/invoices/{invoice.id}/pay"

    first = await async_client.post(url, json=payload, headers=headers)
    replay = await async_client.post(url, json=payload, headers=headers)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    await db.refresh(invoice)
    assert invoice.status == "paid"
    assert await db.scalar(
        select(func.count(SupplierPayment.id)).where(SupplierPayment.invoice_id == invoice.id)
    ) == 1
    assert await db.scalar(
        select(func.count(JournalEntry.id)).where(
            JournalEntry.source_document_type == "supplier_payment",
            JournalEntry.source_document_id == first.json()["id"],
        )
    ) == 1
    assert await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "payables.supplier_payment.created",
            AuditLog.entity_id == first.json()["id"],
        )
    ) == 1


async def test_supplier_payment_rolls_back_when_accounts_are_incomplete(
    async_client, auth_headers, db, tenant_id
):
    invoice = await _seed_payable(db, tenant_id, include_bank_account=False)
    key = f"supplier-payment:{uuid4()}"
    response = await async_client.post(
        f"/api/v1/payables/invoices/{invoice.id}/pay",
        headers={**auth_headers, "Idempotency-Key": key},
        json={
            "amount": "500.00",
            "payment_method": "bank_transfer",
            "value_date": datetime.now(UTC).isoformat(),
        },
    )

    assert response.status_code == 409
    await db.refresh(invoice)
    assert invoice.status == "pending"
    assert await db.scalar(
        select(func.count(SupplierPayment.id)).where(SupplierPayment.invoice_id == invoice.id)
    ) == 0
    assert await db.scalar(
        select(func.count(IdempotencyKey.id)).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.idempotency_key == key,
        )
    ) == 0


async def test_concurrent_payments_cannot_overpay_same_invoice(
    async_client, auth_headers, db, tenant_id
):
    invoice = await _seed_payable(db, tenant_id)
    payload = {
        "amount": "1000.00",
        "payment_method": "bank_transfer",
        "value_date": datetime.now(UTC).isoformat(),
    }
    url = f"/api/v1/payables/invoices/{invoice.id}/pay"

    first, second = await asyncio.gather(
        async_client.post(
            url,
            json={**payload, "reference": "RACE-1"},
            headers={**auth_headers, "Idempotency-Key": f"supplier-payment:{uuid4()}"},
        ),
        async_client.post(
            url,
            json={**payload, "reference": "RACE-2"},
            headers={**auth_headers, "Idempotency-Key": f"supplier-payment:{uuid4()}"},
        ),
    )

    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert await db.scalar(
        select(func.count(SupplierPayment.id)).where(SupplierPayment.invoice_id == invoice.id)
    ) == 1
    assert await db.scalar(
        select(func.count(JournalEntry.id)).where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.source_document_type == "supplier_payment"
        )
    ) == 1
