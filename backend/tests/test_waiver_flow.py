"""BILL-03 waiver lifecycle tests."""

from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_negative_margin_trip_blocked_without_waiver(
    async_client, auth_headers, seed_negative_margin_trip
):
    """BILL-03: Trip with margin < 0 returns 409 when billing is attempted without a waiver."""
    trip = seed_negative_margin_trip
    now = datetime.now(UTC)
    payload = {
        "contract_id": str(trip.contract_id),
        "client_name": "Test Client BILL-03",
        "billing_period_start": (now - timedelta(days=30)).isoformat(),
        "billing_period_end": (now + timedelta(days=1)).isoformat(),
        "trip_ids": [str(trip.id)],
    }
    response = await async_client.post(
        "/api/v1/billing/documents",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "negative_margin_requires_approval"


@pytest.mark.asyncio
async def test_waiver_create_sets_pending_approval(
    async_client, auth_headers, seed_negative_margin_trip
):
    """BILL-03: POST /api/v1/billing/waivers creates a waiver with status='pending_approval'."""
    trip = seed_negative_margin_trip
    payload = {
        "trip_id": str(trip.id),
        "reason": "Justificativa de teste para waiver de margem negativa",
    }
    response = await async_client.post(
        "/api/v1/billing/waivers",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_waiver_approve_allows_billing(async_client, owner_headers, seed_pending_waiver):
    """BILL-03: POST /api/v1/billing/waivers/{id}/approve sets status='active'."""
    waiver = seed_pending_waiver
    response = await async_client.post(
        f"/api/v1/billing/waivers/{waiver.id}/approve",
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_waiver_approve_requires_owner_admin(
    async_client, viewer_headers, seed_pending_waiver
):
    """BILL-03: RBAC — viewer cannot approve a waiver (must return 403)."""
    waiver = seed_pending_waiver
    response = await async_client.post(
        f"/api/v1/billing/waivers/{waiver.id}/approve",
        headers=viewer_headers,
    )
    assert response.status_code == 403
