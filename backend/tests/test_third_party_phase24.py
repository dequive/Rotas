"""Phase 24 hardening — correctness tests for third-party contacts, ledger, and evaluations.

Every test asserts a computed value, not just an HTTP status code.
"""

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from app.database import AsyncSessionLocal
from app.modules.tenants.models import Tenant


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def third_party_id(async_client: AsyncClient, auth_headers: dict) -> str:
    """Create a third party and return its ID for use in sub-resource tests."""
    resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": f"Fornecedor Teste {uuid.uuid4().hex[:6]}"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Failed to create third party: {resp.text}"
    return resp.json()["id"]


@pytest.fixture
async def second_tenant_id():
    """Create an isolated second tenant and return its ID."""
    async with AsyncSessionLocal() as session:
        suffix = uuid.uuid4().hex[:8]
        tenant = Tenant(name=f"Isolado Tenant {suffix}", slug=f"isolado-{suffix}")
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return str(tenant.id)


@pytest.fixture
def second_auth_headers(second_tenant_id: str) -> dict:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": second_tenant_id,
    }


@pytest.fixture
async def second_third_party_id(
    async_client: AsyncClient, second_auth_headers: dict
) -> str:
    resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": f"Terceiro Isolado {uuid.uuid4().hex[:6]}"},
        headers=second_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── BLOCK D tests ─────────────────────────────────────────────────────────────


async def test_create_and_list_contacts(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """POST contact → 201 with correct fields; GET lists it; DELETE removes it."""
    # Create
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/contacts",
        json={
            "name": "Maria Sitoe",
            "role": "Directora",
            "phone": "+258840001111",
            "email": "maria@exemplo.co.mz",
            "is_primary": True,
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201, resp.text
    contact = resp.json()
    assert contact["name"] == "Maria Sitoe"
    assert contact["role"] == "Directora"
    assert contact["phone"] == "+258840001111"
    contact_id = contact["id"]

    # List contains the contact
    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/contacts",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    contacts = resp.json()
    ids = [c["id"] for c in contacts]
    assert contact_id in ids, f"Contact {contact_id} not found in {ids}"

    # Delete
    resp = await async_client.delete(
        f"/api/v1/third-party/{third_party_id}/contacts/{contact_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # List after delete is empty (for this contact)
    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/contacts",
        headers=auth_headers,
    )
    ids_after = [c["id"] for c in resp.json()]
    assert contact_id not in ids_after


async def test_contact_cross_tenant_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    third_party_id: str,
    second_auth_headers: dict,
):
    """Contact created in tenant A must return 404 when accessed from tenant B's third_party."""
    # Create contact in tenant A
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/contacts",
        json={"name": "Contacto A"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201
    contact_id = resp.json()["id"]

    # Try to delete contact from tenant A's third_party using tenant B's credentials
    resp = await async_client.delete(
        f"/api/v1/third-party/{third_party_id}/contacts/{contact_id}",
        headers=second_auth_headers,
    )
    # The third_party belongs to tenant A — tenant B should get 404
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant access, got {resp.status_code}: {resp.text}"
    )


async def test_supplier_account_balance_correctness(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """Balance computation: credits - debits must be exact to 2 decimal places."""
    # Start at zero
    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/account",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["balance"]) == Decimal("0.00")

    # POST a credit of 500.00 MZN
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json={"amount": "500.00", "currency": "MZN", "description": "Pagamento inicial"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201, resp.text
    assert Decimal(resp.json()["amount"]) == Decimal("500.00")

    # Insert a debit entry directly via DB (no public debit endpoint exists)
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.text(
                "INSERT INTO supplier_ledger_entries "
                "(id, tenant_id, third_party_id, entry_type, amount, currency, "
                " source_type, entry_date) "
                "VALUES (gen_random_uuid(), :tid, :tpid, 'debit', 200.00, 'MZN', "
                "        'adjustment', current_date)"
            ),
            {"tid": auth_headers["X-Tenant-Id"], "tpid": third_party_id},
        )
        await session.commit()

    # Check account
    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/account",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["total_credits"]) == Decimal("500.00")
    assert Decimal(data["total_debits"]) == Decimal("200.00")
    assert Decimal(data["balance"]) == Decimal("300.00")
    # Currency grouping
    assert "MZN" in data["balances"]
    assert Decimal(data["balances"]["MZN"]["balance"]) == Decimal("300.00")


async def test_supplier_account_multi_currency(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """MZN and USD balances are tracked separately — no cross-currency summation."""
    # Post 1000 MZN
    await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json={"amount": "1000.00", "currency": "MZN"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    # Post 200 USD
    await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json={"amount": "200.00", "currency": "USD"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/account",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    balances = data["balances"]

    assert "MZN" in balances, f"MZN missing from balances: {balances}"
    assert "USD" in balances, f"USD missing from balances: {balances}"
    assert Decimal(balances["MZN"]["balance"]) == Decimal("1000.00")
    assert Decimal(balances["USD"]["balance"]) == Decimal("200.00")
    # The two currencies must never be summed together
    assert Decimal(balances["MZN"]["balance"]) != Decimal("1200.00")


async def test_create_payment_idempotency_replay(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """Same Idempotency-Key → cached response, not a second ledger entry."""
    idem_key = f"test-idem-payment-{uuid.uuid4().hex}"
    payload = {"amount": "750.00", "currency": "MZN", "description": "Idem test"}

    r1 = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json=payload,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert r1.status_code == 201

    r2 = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json=payload,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    # Replay must return 2xx (200 or 201 depending on implementation)
    assert r2.status_code in (200, 201), f"Unexpected status on replay: {r2.status_code}"
    assert r2.json()["id"] == r1.json()["id"], "Idempotent replay returned a different entry"

    # Confirm only ONE ledger entry exists for this exact amount/desc combo via account endpoint
    account_resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/account",
        headers=auth_headers,
    )
    entries = account_resp.json()["entries"]
    matching = [e for e in entries if e["amount"] == "750.00" and e["description"] == "Idem test"]
    assert len(matching) == 1, f"Expected 1 ledger entry for idem key, found {len(matching)}"


async def test_create_evaluation_score_correctness(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """Weighted score = sum(weight * score) rounded to 2 dp."""
    criteria = [
        {"name": "prazo", "weight": 0.6, "score": 8.0},
        {"name": "qualidade", "weight": 0.4, "score": 5.0},
    ]
    # Expected: 0.6*8.0 + 0.4*5.0 = 4.8 + 2.0 = 6.80
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={"criteria": criteria, "evaluation_date": "2026-06-20"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201, resp.text
    ev = resp.json()
    assert Decimal(ev["score"]) == Decimal("6.80"), (
        f"Expected score 6.80, got {ev['score']}"
    )


async def test_create_evaluation_invalid_criteria_rejected(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """Negative weight, out-of-range score, and wrong sum all return 422."""
    base_idem = lambda: {**auth_headers, "Idempotency-Key": str(uuid.uuid4())}

    # Negative weight
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={"criteria": [{"name": "prazo", "weight": -0.5, "score": 5.0}]},
        headers=base_idem(),
    )
    assert resp.status_code == 422, f"Negative weight should be 422, got {resp.status_code}"

    # Score > 10
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={"criteria": [{"name": "prazo", "weight": 1.0, "score": 11.0}]},
        headers=base_idem(),
    )
    assert resp.status_code == 422, f"Score > 10 should be 422, got {resp.status_code}"

    # Weights summing to 0.5 (not 1.0)
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={
            "criteria": [
                {"name": "a", "weight": 0.25, "score": 5.0},
                {"name": "b", "weight": 0.25, "score": 5.0},
            ]
        },
        headers=base_idem(),
    )
    assert resp.status_code == 422, f"Weights summing to 0.5 should be 422, got {resp.status_code}"


async def test_create_evaluation_idempotency_replay(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """Same Idempotency-Key → cached evaluation, not a second record."""
    idem_key = f"test-idem-eval-{uuid.uuid4().hex}"
    criteria = [{"name": "entrega", "weight": 1.0, "score": 7.0}]
    payload = {"criteria": criteria, "evaluation_date": "2026-06-20"}

    r1 = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json=payload,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert r1.status_code == 201

    r2 = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json=payload,
        headers={**auth_headers, "Idempotency-Key": idem_key},
    )
    assert r2.status_code in (200, 201)
    assert r2.json()["id"] == r1.json()["id"]

    # Only ONE evaluation in the list
    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        headers=auth_headers,
    )
    evals = resp.json()["evaluations"]
    matching = [e for e in evals if e["id"] == r1.json()["id"]]
    assert len(matching) == 1, f"Expected 1 evaluation, found {len(matching)}"


async def test_list_evaluations_average_score(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """average_score = arithmetic mean of all evaluation scores."""
    # Evaluation 1: score = 6.80
    await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={
            "criteria": [
                {"name": "prazo", "weight": 0.6, "score": 8.0},
                {"name": "qualidade", "weight": 0.4, "score": 5.0},
            ]
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    # Evaluation 2: score = 8.00
    await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={
            "criteria": [{"name": "geral", "weight": 1.0, "score": 8.0}]
        },
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # (6.80 + 8.00) / 2 = 7.40
    assert Decimal(data["average_score"]) == Decimal("7.40"), (
        f"Expected average 7.40, got {data['average_score']}"
    )


async def test_ledger_immutability(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """DB trigger must prevent UPDATE and DELETE on supplier_ledger_entries."""
    # Create a payment first
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json={"amount": "100.00", "currency": "MZN"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201
    entry_id = resp.json()["id"]

    async with AsyncSessionLocal() as session:
        # UPDATE must raise
        with pytest.raises(Exception, match="immutable"):
            await session.execute(
                sa.text(
                    "UPDATE supplier_ledger_entries SET amount = 999.00 WHERE id = :eid"
                ),
                {"eid": entry_id},
            )
            await session.commit()

    async with AsyncSessionLocal() as session:
        # DELETE must raise
        with pytest.raises(Exception, match="immutable"):
            await session.execute(
                sa.text("DELETE FROM supplier_ledger_entries WHERE id = :eid"),
                {"eid": entry_id},
            )
            await session.commit()


async def test_evaluation_immutability(
    async_client: AsyncClient, auth_headers: dict, third_party_id: str
):
    """DB trigger must prevent UPDATE and DELETE on supplier_evaluations."""
    resp = await async_client.post(
        f"/api/v1/third-party/{third_party_id}/evaluations",
        json={"criteria": [{"name": "geral", "weight": 1.0, "score": 7.0}]},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 201
    eval_id = resp.json()["id"]

    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception, match="immutable"):
            await session.execute(
                sa.text(
                    "UPDATE supplier_evaluations SET score = 0.00 WHERE id = :eid"
                ),
                {"eid": eval_id},
            )
            await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception, match="immutable"):
            await session.execute(
                sa.text("DELETE FROM supplier_evaluations WHERE id = :eid"),
                {"eid": eval_id},
            )
            await session.commit()


async def test_account_cross_tenant_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    third_party_id: str,
    second_auth_headers: dict,
):
    """Ledger entries of tenant A are invisible from tenant B."""
    # Create payment in tenant A
    await async_client.post(
        f"/api/v1/third-party/{third_party_id}/payments",
        json={"amount": "9999.00", "currency": "MZN"},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )

    # Tenant B trying to access tenant A's third_party account → 404
    resp = await async_client.get(
        f"/api/v1/third-party/{third_party_id}/account",
        headers=second_auth_headers,
    )
    assert resp.status_code == 404, (
        f"Tenant B should get 404 for tenant A's third_party, got {resp.status_code}"
    )
