from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.passwords import hash_password
from app.modules.notifications.models import NotificationOutbox
from app.modules.tenants.models import Tenant
from app.modules.users.models import User


async def create_user(db):
    suffix = uuid4().hex[:8]
    tenant = Tenant(name=f"Tenant Reset {suffix}", slug=f"reset-{suffix}")
    db.add(tenant)
    await db.flush()
    user = User(
        tenant_id=tenant.id,
        email=f"owner-reset-{suffix}@example.test",
        password_hash=hash_password("old-password"),
        full_name="Owner Reset",
        role="owner",
    )
    db.add(user)
    await db.commit()
    return tenant, user


@pytest.mark.asyncio
async def test_password_reset_request_does_not_enumerate_unknown_email(async_client) -> None:
    response = await async_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "missing@example.test"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_password_reset_completes_and_revokes_old_password(db, async_client) -> None:
    tenant, user = await create_user(db)

    request_response = await async_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": user.email, "tenant_slug": tenant.slug},
    )
    assert request_response.status_code == 200
    reset_token = request_response.json()["reset_token"]
    reset_url = request_response.json()["reset_url"]
    assert reset_token in reset_url

    notification = await db.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.tenant_id == tenant.id,
            NotificationOutbox.template == "password_reset",
        )
    )
    assert notification is not None
    assert notification.recipient == user.email
    assert reset_url in notification.body_text

    complete_response = await async_client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": reset_token, "new_password": "new-password"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json() == {"ok": True}

    old_login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "old-password", "tenant_slug": tenant.slug},
    )
    assert old_login_response.status_code == 401

    new_login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "new-password", "tenant_slug": tenant.slug},
    )
    assert new_login_response.status_code == 200

    replay_response = await async_client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": reset_token, "new_password": "another-password"},
    )
    assert replay_response.status_code == 401
