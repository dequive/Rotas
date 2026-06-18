from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.modules.notifications.schemas import EmailNotificationCreate
from app.modules.notifications.service import enqueue_email
from app.modules.tenants.models import Tenant


async def create_tenant(db):
    suffix = uuid4().hex[:8]
    tenant = Tenant(name=f"Tenant Notify {suffix}", slug=f"notify-{suffix}")
    db.add(tenant)
    await db.commit()
    return tenant


@pytest.mark.asyncio
async def test_enqueue_email_is_idempotent_for_same_reference(db) -> None:
    tenant = await create_tenant(db)
    payload = EmailNotificationCreate(
        request_reference="welcome:test",
        recipient="owner@example.test",
        subject="Bem-vindo ao ROTAS",
        body_text="Conta criada.",
        template="welcome",
    )

    first = await enqueue_email(db, tenant.id, payload)
    second = await enqueue_email(db, tenant.id, payload)

    assert second["id"] == first["id"]
    assert second["status"] == "queued"


@pytest.mark.asyncio
async def test_enqueue_email_rejects_reference_reuse_with_different_payload(db) -> None:
    tenant = await create_tenant(db)
    await enqueue_email(
        db,
        tenant.id,
        EmailNotificationCreate(
            request_reference="welcome:conflict",
            recipient="owner@example.test",
            subject="Bem-vindo ao ROTAS",
            body_text="Conta criada.",
        ),
    )

    with pytest.raises(ApiError) as exc_info:
        await enqueue_email(
            db,
            tenant.id,
            EmailNotificationCreate(
                request_reference="welcome:conflict",
                recipient="other@example.test",
                subject="Bem-vindo ao ROTAS",
                body_text="Conta criada.",
            ),
        )

    assert exc_info.value.code == "notification_request_reference_reused"
