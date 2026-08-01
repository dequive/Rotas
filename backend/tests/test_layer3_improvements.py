import uuid
from unittest.mock import AsyncMock

import pytest

from app.main import app
from app.modules.clients.models import Client
from app.modules.contracts.models import Contract


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    redis.keys = AsyncMock(return_value=[])
    return redis


@pytest.mark.asyncio
async def test_client_nuit_phone_email_and_cache(
    async_client, db, tenant_id, auth_headers, mock_redis
):
    # Attach mock redis to app state
    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # 1. Valid client creation should normalize NUIT, phone, and email
        payload = {
            "trading_name": f"Client Layer 3 {uuid.uuid4().hex[:6]}",
            "legal_name": "Client Layer 3 Lda",
            "nuit": " 400-123-456 ",  # Should be normalized to "400123456"
            "phone": "  84 123 4567  ",  # Should be normalized to "+258841234567"
            "email": "  TEST@Client.co.mz  ",  # Should be normalized to "test@client.co.mz"
            "payment_terms_days": 30,
            "credit_limit": "5000.00",
        }
        response = await async_client.post("/api/v1/clients", json=payload, headers=auth_headers)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["nuit"] == "400123456"
        assert data["phone"] == "+258841234567"
        assert data["email"] == "test@client.co.mz"

        # Verify cache invalidation was triggered
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")
        mock_redis.delete.reset_mock()

        # 2. Invalid NUIT formats should be rejected with 422
        bad_payload = payload.copy()
        bad_payload["nuit"] = "12345678"  # Only 8 digits
        response2 = await async_client.post(
            "/api/v1/clients", json=bad_payload, headers=auth_headers
        )
        assert response2.status_code == 422

        # 3. Patch client should normalize phone and email, and invalidate cache
        client_id = data["id"]
        patch_payload = {"phone": " 82 999 0000 ", "email": " UPDATE@client.co.mz "}
        response3 = await async_client.patch(
            f"/api/v1/clients/{client_id}", json=patch_payload, headers=auth_headers
        )
        assert response3.status_code == 200, response3.text
        data3 = response3.json()
        assert data3["phone"] == "+258829990000"
        assert data3["email"] == "update@client.co.mz"

        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

    finally:
        app.state.redis = old_redis


@pytest.mark.asyncio
async def test_third_party_nuit_phone_email_and_cache(
    async_client, db, tenant_id, auth_headers, mock_redis
):
    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # 1. Valid Third Party creation should normalize NUIT, phone, and email
        payload = {
            "name": f"Supplier Layer 3 {uuid.uuid4().hex[:6]}",
            "nuit": " 400 999 111 ",
            "contact_phone": " 82 999 2222 ",
            "contact_email": " FORNECEDOR@TESTE.COM ",
            "status": "active",
        }
        response = await async_client.post(
            "/api/v1/third-party", json=payload, headers=auth_headers
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["nuit"] == "400999111"
        assert data["contact_phone"] == "+258829992222"
        assert data["contact_email"] == "fornecedor@teste.com"

        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")
        mock_redis.delete.reset_mock()

        # 2. Invalid NUIT should be rejected
        bad_payload = payload.copy()
        bad_payload["nuit"] = "400-abc-def"
        response2 = await async_client.post(
            "/api/v1/third-party", json=bad_payload, headers=auth_headers
        )
        assert response2.status_code == 422

        # 3. Patch third party normalizes email/phone & invalidates cache
        tp_id = data["id"]
        patch_payload = {"contact_phone": " 87 111 2222 ", "contact_email": " UPDATE@TESTE.COM "}
        response3 = await async_client.patch(
            f"/api/v1/third-party/{tp_id}", json=patch_payload, headers=auth_headers
        )
        assert response3.status_code == 200, response3.text
        data3 = response3.json()
        assert data3["contact_phone"] == "+258871112222"
        assert data3["contact_email"] == "update@teste.com"

        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

    finally:
        app.state.redis = old_redis


@pytest.mark.asyncio
async def test_contract_nuit_date_validation_and_cache(
    async_client, db, tenant_id, auth_headers, mock_redis
):
    # Seed a client first
    client = Client(
        tenant_id=tenant_id, trading_name="Client for Layer 3 Contract", nuit="400999123"
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # 1. Valid contract creation should normalize NUIT
        payload = {
            "client_id": str(client.id),
            "client_name": "Client for Layer 3 Contract",
            "client_nuit": " 400-999-123 ",
            "contract_reference": f"CTR-L3-{uuid.uuid4().hex[:6]}",
            "title": "Contract Title",
            "starts_at": "2026-01-01T00:00:00",
            "ends_at": "2026-12-31T23:59:59",
        }
        response = await async_client.post("/api/v1/contracts/", json=payload, headers=auth_headers)
        assert response.status_code in (200, 201), response.text
        data = response.json()

        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")
        mock_redis.delete.reset_mock()

        # 2. Invalid date range (ends_at <= starts_at)
        bad_date_payload = payload.copy()
        bad_date_payload["contract_reference"] = f"CTR-L3-BAD-{uuid.uuid4().hex[:6]}"
        bad_date_payload["ends_at"] = "2025-12-31T23:59:59"
        response2 = await async_client.post(
            "/api/v1/contracts/", json=bad_date_payload, headers=auth_headers
        )
        assert response2.status_code == 422

        # 3. Invalid NUIT format
        bad_nuit_payload = payload.copy()
        bad_nuit_payload["contract_reference"] = f"CTR-L3-NUIT-{uuid.uuid4().hex[:6]}"
        bad_nuit_payload["client_nuit"] = "999-888"
        response3 = await async_client.post(
            "/api/v1/contracts/", json=bad_nuit_payload, headers=auth_headers
        )
        assert response3.status_code == 422

        # 4. Patch contract validation
        contract_id = data["id"]
        patch_payload = {
            "starts_at": "2026-06-01T00:00:00",
            "ends_at": "2026-05-31T23:59:59",  # invalid range
        }
        response4 = await async_client.patch(
            f"/api/v1/contracts/{contract_id}", json=patch_payload, headers=auth_headers
        )
        assert response4.status_code == 422

        # Valid patch should invalidate cache
        patch_payload_valid = {"ends_at": "2026-10-31T23:59:59"}
        response5 = await async_client.patch(
            f"/api/v1/contracts/{contract_id}", json=patch_payload_valid, headers=auth_headers
        )
        assert response5.status_code in (200, 201)

        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

    finally:
        app.state.redis = old_redis


@pytest.mark.asyncio
async def test_billing_document_nuit_and_periods(
    async_client, db, tenant_id, auth_headers, mock_redis
):
    # Seed a contract
    contract = Contract(
        tenant_id=tenant_id,
        client_name="Client for Billing",
        contract_reference=f"CTR-BILL-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)

    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # 1. Valid Billing Document Create
        payload = {
            "contract_id": str(contract.id),
            "client_name": "Fatura Client",
            "contract_reference": contract.contract_reference,
            "billing_period_start": "2026-06-01T00:00:00",
            "billing_period_end": "2026-06-30T23:59:59",
            "client_nuit": " 400-333-222 ",
            "currency": "MZN",
            "trip_ids": [],
        }
        response = await async_client.post(
            "/api/v1/billing/documents", json=payload, headers=auth_headers
        )
        assert response.status_code in (200, 201), response.text
        data = response.json()
        assert data["client_nuit"] == "400333222"

        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")
        mock_redis.delete.reset_mock()

        # 2. Invalid Period (end <= start)
        bad_period_payload = payload.copy()
        bad_period_payload["billing_period_end"] = "2026-05-31T23:59:59"
        response2 = await async_client.post(
            "/api/v1/billing/documents", json=bad_period_payload, headers=auth_headers
        )
        assert response2.status_code == 422

        # 3. Invalid NUIT
        bad_nuit_payload = payload.copy()
        bad_nuit_payload["client_nuit"] = "abc"
        response3 = await async_client.post(
            "/api/v1/billing/documents", json=bad_nuit_payload, headers=auth_headers
        )
        assert response3.status_code == 422

    finally:
        app.state.redis = old_redis
