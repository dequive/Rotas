from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.modules.audit.models import AuditLog
from app.modules.notifications.models import NotificationOutbox
from app.modules.tenants.models import Tenant
from app.modules.users.models import User


@pytest.mark.asyncio
async def test_public_onboarding_creates_trial_tenant_owner_and_tokens(async_client):
    suffix = uuid4().hex[:8]
    response = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Transportes Self Service {suffix}",
            "company_slug": f"self-service-{suffix}",
            "company_nuit": "400000001",
            "owner_full_name": "Ana Owner",
            "owner_email": f"owner-{suffix}@example.test",
            "owner_password": "secure-password",
            "phone": "258840000001",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["tenant"]["slug"] == f"self-service-{suffix}"
    assert payload["tenant"]["plan"] == "trial"
    assert payload["tenant"]["trial_ends_at"]
    assert payload["owner"]["role"] == "owner"
    assert payload["owner"]["email_verified_at"] is None
    assert payload["verification_token"]
    assert payload["verification_url"]
    assert payload["access_token"]
    assert payload["refresh_token"]

    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == f"self-service-{suffix}"))
        assert tenant is not None
        owner = await db.scalar(select(User).where(User.tenant_id == tenant.id))
        assert owner is not None
        assert owner.email == f"owner-{suffix}@example.test"
        assert owner.email_verified_at is None
        notification = await db.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.tenant_id == tenant.id,
                NotificationOutbox.template == "email_verification",
            )
        )
        assert notification is not None
        assert notification.recipient == owner.email
        assert payload["verification_url"] in notification.body_text
        actions = set(
            (
                await db.scalars(
                    select(AuditLog.action).where(AuditLog.tenant_id == tenant.id)
                )
            ).all()
        )
        assert {"tenant.self_registered", "user.owner_created"}.issubset(actions)

    verify_response = await async_client.post(
        "/api/v1/onboarding/verify-email",
        json={"token": payload["verification_token"]},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["ok"] is True

    replay_response = await async_client.post(
        "/api/v1/onboarding/verify-email",
        json={"token": payload["verification_token"]},
    )
    assert replay_response.status_code == 401

    async with AsyncSessionLocal() as db:
        owner = await db.scalar(select(User).where(User.email == f"owner-{suffix}@example.test"))
        assert owner is not None
        assert owner.email_verified_at is not None


@pytest.mark.asyncio
async def test_public_onboarding_rejects_duplicate_slug(async_client):
    suffix = uuid4().hex[:8]
    payload = {
        "company_name": f"Primeiro Tenant {suffix}",
        "company_slug": f"duplicate-{suffix}",
        "owner_full_name": "Owner One",
        "owner_email": f"one-{suffix}@example.test",
        "owner_password": "secure-password",
    }
    first = await async_client.post("/api/v1/onboarding/register", json=payload)
    assert first.status_code == 201

    second = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            **payload,
            "company_name": f"Segundo Tenant {suffix}",
            "owner_email": f"two-{suffix}@example.test",
        },
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "tenant_slug_conflict"
