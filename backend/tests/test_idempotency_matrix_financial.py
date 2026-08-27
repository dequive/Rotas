"""F7.4: replay and payload-conflict matrix over the financial mutations.

Separate module from `test_idempotency_matrix.py` because these mutations are
not reachable with cheap seeding: an adjustment note needs an *issued* invoice,
a client payment needs a client, and a driver advance needs a trip the driver
is actually assigned to.

The stakes are also different. A duplicate vehicle is noise; a duplicate credit
note is a fiscal document with its own sequential number issued against the
same invoice, and a duplicate advance is money paid twice to the same driver
for the same trip.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.database import import_all_models
from app.modules.billing import service as billing_service
from app.modules.billing.models import BillingDocument, BillingItem, ClientPayment
from app.modules.billing.schemas import IssueBillingDocumentRequest
from app.modules.cargo.models import DeliveryProof
from app.modules.clients.models import Client
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver, DriverAdvance
from app.modules.third_party.models import SupplierLedgerEntry, ThirdParty
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

import_all_models()


def _suffix() -> str:
    return uuid4().hex[:8]


class FinancialCase:
    def __init__(
        self,
        name: str,
        path: Callable[[dict], str],
        model: Any,
        payload: Callable[[dict], dict],
        mutated: Callable[[dict], dict],
        expected_status: tuple[int, ...] = (200, 201),
        duplicate_without_key: str = "writes_twice",
    ) -> None:
        self.name = name
        self._path = path
        self.model = model
        self.payload = payload
        self.mutated = mutated
        self.expected_status = expected_status
        # What the endpoint does when the same payload is posted twice with no
        # key: "writes_twice" (nothing else protects it) or a domain error code
        # that already blocks the duplicate on its own.
        self.duplicate_without_key = duplicate_without_key

    def path(self, ctx: dict) -> str:
        return self._path(ctx)

    def __repr__(self) -> str:  # pragma: no cover - pytest id only
        return self.name


CASES: list[FinancialCase] = [
    FinancialCase(
        name="billing.debit_note.create",
        path=lambda ctx: f"/api/v1/billing/documents/{ctx['issued_document_id']}/debit-note",
        model=BillingDocument,
        payload=lambda ctx: {"amount": "500.00", "reason": "Sobrecarga de espera na descarga"},
        mutated=lambda ctx: {"amount": "900.00", "reason": "Sobrecarga de espera na descarga"},
    ),
    FinancialCase(
        name="billing.credit_note.create",
        path=lambda ctx: f"/api/v1/billing/documents/{ctx['issued_document_id']}/credit-note",
        model=BillingDocument,
        payload=lambda ctx: {"amount": "250.00", "reason": "Desconto comercial acordado"},
        mutated=lambda ctx: {"amount": "400.00", "reason": "Desconto comercial acordado"},
    ),
    FinancialCase(
        name="billing.payment.register",
        path=lambda ctx: "/api/v1/billing/payments",
        model=ClientPayment,
        payload=lambda ctx: {
            "client_id": str(ctx["client_id"]),
            "amount": "1500.00",
            "currency": "MZN",
            "value_date": ctx["value_date"],
            "payment_method": "bank_transfer",
            "reference": f"TRF-{ctx['suffix'].upper()}",
        },
        mutated=lambda ctx: {
            "client_id": str(ctx["client_id"]),
            "amount": "2500.00",
            "currency": "MZN",
            "value_date": ctx["value_date"],
            "payment_method": "bank_transfer",
            "reference": f"TRF-{ctx['suffix'].upper()}",
        },
    ),
    FinancialCase(
        name="third_party.payment.create",
        path=lambda ctx: f"/api/v1/third-party/{ctx['third_party_id']}/payments",
        model=SupplierLedgerEntry,
        payload=lambda ctx: {
            "amount": "3000.00",
            "currency": "MZN",
            "description": f"Pagamento {ctx['suffix']}",
        },
        mutated=lambda ctx: {
            "amount": "7000.00",
            "currency": "MZN",
            "description": f"Pagamento {ctx['suffix']}",
        },
    ),
    FinancialCase(
        name="driver_advance.issue",
        path=lambda ctx: f"/api/v1/trips/{ctx['trip_id']}/advance",
        model=DriverAdvance,
        payload=lambda ctx: {
            "driver_id": str(ctx["driver_id"]),
            "amount_mzn": "5000.00",
            "allowance_mzn": "2000.00",
            "expenses_mzn": "3000.00",
        },
        mutated=lambda ctx: {
            "driver_id": str(ctx["driver_id"]),
            "amount_mzn": "8000.00",
            "allowance_mzn": "3000.00",
            "expenses_mzn": "5000.00",
        },
        # One non-voided advance per trip is a domain invariant, so a duplicate
        # is refused even with no key. The key still changes the outcome — see
        # test_key_turns_domain_conflict_into_replay.
        duplicate_without_key="advance_already_exists",
    ),
]


async def build_financial_context(db, owner_tenant_id: UUID) -> dict:
    """Seed the full chain a financial mutation hangs off, for one tenant.

    Everything is created for `owner_tenant_id` on purpose: a payload pointing
    at another tenant's invoice is rejected before the idempotency layer is
    reached, which would hide the property under test.
    """
    suffix = _suffix()
    now = datetime.now(UTC)

    client = Client(
        tenant_id=owner_tenant_id,
        trading_name=f"Cliente {suffix}",
        nuit=f"4003{uuid4().int % 100000:05d}",
    )
    contract = Contract(
        tenant_id=owner_tenant_id,
        client_name=f"Cliente {suffix}",
        contract_reference=f"REF-{suffix.upper()}",
        status="active",
    )
    vehicle = Vehicle(tenant_id=owner_tenant_id, plate=f"FIN-{suffix.upper()}", status="active")
    driver = Driver(tenant_id=owner_tenant_id, full_name=f"Motorista {suffix}", status="active")
    third_party = ThirdParty(
        tenant_id=owner_tenant_id,
        name=f"Fornecedor {suffix}",
        nuit=f"4004{uuid4().int % 100000:05d}",
        status="active",
    )
    db.add_all([client, contract, vehicle, driver, third_party])
    await db.flush()

    # Trip the advance is issued against — must not be completed yet.
    trip = Trip(
        tenant_id=owner_tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        contract_id=contract.id,
        origin="Maputo",
        destination="Beira",
        status="planned",
        billing_status="pending_delivery_proof",
    )
    db.add(trip)
    await db.flush()

    # Invoice the adjustment notes hang off — a note requires an issued parent.
    document = BillingDocument(
        tenant_id=owner_tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="draft",
        currency="MZN",
        client_nuit="400123456",
    )
    db.add(document)
    await db.flush()

    billed_trip = Trip(
        tenant_id=owner_tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        contract_id=contract.id,
        origin="Maputo",
        destination="Nampula",
        status="draft",
        billing_status="pending_delivery_proof",
    )
    db.add(billed_trip)
    await db.flush()

    db.add(
        BillingItem(
            tenant_id=owner_tenant_id,
            contract_id=contract.id,
            billing_document_id=document.id,
            trip_id=billed_trip.id,
            origin="Maputo",
            destination="Nampula",
            amount=Decimal("1000.00"),
            iva_rate=Decimal("0.1700"),
            iva_amount=Decimal("170.00"),
            delivered_at=now,
            status="pending",
        )
    )
    await db.flush()

    await billing_service.issue_document(db, owner_tenant_id, document.id, IssueBillingDocumentRequest())
    await db.commit()

    # A second draft invoice, kept unissued so `issue` has something to act on.
    draft = BillingDocument(
        tenant_id=owner_tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=60),
        billing_period_end=now - timedelta(days=31),
        status="draft",
        currency="MZN",
        client_nuit="400123456",
    )
    db.add(draft)
    await db.flush()
    db.add(
        BillingItem(
            tenant_id=owner_tenant_id,
            contract_id=contract.id,
            billing_document_id=draft.id,
            trip_id=billed_trip.id,
            origin="Maputo",
            destination="Nampula",
            amount=Decimal("500.00"),
            iva_rate=Decimal("0.1700"),
            iva_amount=Decimal("85.00"),
            delivered_at=now,
            status="pending",
        )
    )

    proof = DeliveryProof(
        tenant_id=owner_tenant_id,
        trip_id=trip.id,
        proof_type="client_discharge_note",
        client_type="company",
        receiver_name="Armazem Beira",
        delivered_at=now,
        cargo_condition="intact",
        quantity_delivered=Decimal("400.00"),
        status="pending_validation",
    )
    db.add(proof)
    await db.commit()

    return {
        "suffix": suffix,
        "draft_document_id": draft.id,
        "delivery_proof_id": proof.id,
        "client_id": client.id,
        "contract_id": contract.id,
        "driver_id": driver.id,
        "trip_id": trip.id,
        "third_party_id": third_party.id,
        "issued_document_id": document.id,
        "value_date": date.today().isoformat(),
    }


@pytest.fixture
async def financial_context(db, tenant_id) -> dict:
    return await build_financial_context(db, tenant_id)


async def _count(db, model: Any, tenant_id: UUID) -> int:
    return await db.scalar(select(func.count(model.id)).where(model.tenant_id == tenant_id))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_financial_replay_writes_once(
    case: FinancialCase, async_client, auth_headers, db, tenant_id, financial_context
) -> None:
    """Same key + same payload: one fiscal effect, not two."""
    key = f"{case.name}:{uuid4().hex}"
    headers = {**auth_headers, "Idempotency-Key": key}
    body = case.payload(financial_context)
    path = case.path(financial_context)

    before = await _count(db, case.model, tenant_id)

    first = await async_client.post(path, json=body, headers=headers)
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"

    replay = await async_client.post(path, json=body, headers=headers)
    assert replay.status_code in case.expected_status, f"{case.name}: {replay.text}"
    assert replay.json().get("id") == first.json().get("id"), f"{case.name}: replay devolveu outro documento"

    after = await _count(db, case.model, tenant_id)
    assert after == before + 1, f"{case.name}: replay criou um segundo registo financeiro — {before} -> {after}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_financial_conflict_is_rejected(
    case: FinancialCase, async_client, auth_headers, db, tenant_id, financial_context
) -> None:
    """Same key + a different amount must never return the first response."""
    key = f"{case.name}:{uuid4().hex}"
    headers = {**auth_headers, "Idempotency-Key": key}
    path = case.path(financial_context)

    first = await async_client.post(path, json=case.payload(financial_context), headers=headers)
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"

    after_first = await _count(db, case.model, tenant_id)

    conflict = await async_client.post(path, json=case.mutated(financial_context), headers=headers)
    assert conflict.status_code == 409, (
        f"{case.name}: montante divergente aceite com {conflict.status_code} — {conflict.text}"
    )
    assert conflict.json()["error"]["code"] == "idempotency_key_reused", conflict.text

    assert await _count(db, case.model, tenant_id) == after_first, f"{case.name}: o conflito escreveu na base"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_without_key_the_same_payload_writes_twice(
    case: FinancialCase, async_client, auth_headers, db, tenant_id, financial_context
) -> None:
    """Negative control: the matrix must be observing the key, not a coincidence.

    Without `Idempotency-Key` the same payload posted twice has to produce two
    rows. If it did not, the replay assertions above would pass for a reason
    that has nothing to do with idempotency — a unique constraint, a dedupe
    somewhere else, or a handler that silently no-ops — and the matrix would be
    proving nothing.
    """
    body = case.payload(financial_context)
    path = case.path(financial_context)

    before = await _count(db, case.model, tenant_id)

    first = await async_client.post(path, json=body, headers=auth_headers)
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"
    second = await async_client.post(path, json=body, headers=auth_headers)

    after = await _count(db, case.model, tenant_id)

    if case.duplicate_without_key == "writes_twice":
        assert second.status_code in case.expected_status, f"{case.name}: {second.text}"
        assert after == before + 2, (
            f"{case.name}: sem chave esperavam-se dois registos, obtiveram-se "
            f"{after - before}. O teste de replay nao esta a medir a chave."
        )
    else:
        assert second.status_code == 409, (
            f"{case.name}: esperava-se o guarda de dominio {case.duplicate_without_key}, obteve-se {second.status_code}"
        )
        assert second.json()["error"]["code"] == case.duplicate_without_key, second.text
        assert after == before + 1, f"{case.name}: o guarda de dominio deixou passar uma segunda escrita"


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if c.duplicate_without_key != "writes_twice"],
    ids=lambda c: c.name,
)
async def test_key_turns_domain_conflict_into_replay(
    case: FinancialCase, async_client, auth_headers, db, tenant_id, financial_context
) -> None:
    """Where a domain rule already blocks the duplicate, the key still matters.

    Without a key the retry gets 409 and the caller cannot tell a lost response
    from a real double-issue. With the key it gets the original success
    response back, which is the whole point of retrying safely over a flaky
    Mozambican mobile link.
    """
    path = case.path(financial_context)
    body = case.payload(financial_context)
    key = f"{case.name}:replay:{uuid4().hex}"

    first = await async_client.post(path, json=body, headers={**auth_headers, "Idempotency-Key": key})
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"

    with_key = await async_client.post(path, json=body, headers={**auth_headers, "Idempotency-Key": key})
    assert with_key.status_code in case.expected_status, (
        f"{case.name}: com chave, a repeticao devolveu {with_key.status_code} "
        f"em vez da resposta guardada — {with_key.text}"
    )
    assert with_key.json()["id"] == first.json()["id"]

    without_key = await async_client.post(path, json=body, headers=auth_headers)
    assert without_key.status_code == 409, f"{case.name}: sem chave esperava-se o guarda de dominio"


# ── Transitions ───────────────────────────────────────────────────────────────
# Issuing an invoice and validating a delivery proof create no row: they change
# the state of one. Counting rows would prove nothing here, so these assert the
# state directly and stay out of the matrix above — folding them in would have
# weakened its row assertion for every case that really is a create.


async def _status_of(db, model: Any, entity_id: UUID) -> str | None:
    return await db.scalar(select(model.status).where(model.id == entity_id))


async def test_replaying_an_issue_does_not_number_the_invoice_twice(
    async_client, auth_headers, db, tenant_id, financial_context
) -> None:
    """A second issue would take a second number in the AT sequential series."""
    document_id = financial_context["draft_document_id"]
    path = f"/api/v1/billing/documents/{document_id}/issue"
    headers = {**auth_headers, "Idempotency-Key": f"issue:{uuid4().hex}"}

    assert await _status_of(db, BillingDocument, document_id) == "draft"

    first = await async_client.post(path, json={}, headers=headers)
    assert first.status_code in (200, 201), first.text
    issued_number = first.json().get("invoice_number")
    assert issued_number, "a emissao nao atribuiu numero de factura"

    replay = await async_client.post(path, json={}, headers=headers)
    assert replay.status_code in (200, 201), replay.text
    assert replay.json().get("invoice_number") == issued_number, (
        "a repeticao atribuiu um segundo numero a mesma factura"
    )

    documents_with_that_number = await db.scalar(
        select(func.count(BillingDocument.id)).where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.invoice_number == issued_number,
        )
    )
    assert documents_with_that_number == 1, "existe mais do que um documento com o mesmo numero de factura"


async def test_replaying_a_delivery_validation_keeps_one_validation(
    async_client, auth_headers, db, tenant_id, financial_context
) -> None:
    proof_id = financial_context["delivery_proof_id"]
    path = f"/api/v1/trips/{financial_context['trip_id']}/delivery-proof/{proof_id}/validate"
    headers = {**auth_headers, "Idempotency-Key": f"validate:{uuid4().hex}"}

    first = await async_client.post(path, json={"validation_method": "manual_review"}, headers=headers)
    assert first.status_code in (200, 201), first.text

    db.expire_all()
    state_after_first = await _status_of(db, DeliveryProof, proof_id)

    replay = await async_client.post(path, json={"validation_method": "manual_review"}, headers=headers)
    assert replay.status_code in (200, 201), replay.text

    db.expire_all()
    assert await _status_of(db, DeliveryProof, proof_id) == state_after_first, (
        "a repeticao alterou o estado da prova de entrega"
    )
