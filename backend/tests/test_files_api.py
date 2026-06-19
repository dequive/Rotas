from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.tenants.models import Tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_tenant() -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Files {suffix}", slug=f"files-{suffix}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_local_file_upload_and_get_are_tenant_scoped() -> None:
    tenant = await create_tenant()
    other_tenant = await create_tenant()

    async with await create_api_client() as client:
        upload_response = await client.post(
            "/api/v1/files/upload",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "file:upload:receipt:001"},
            data={"file_type": "receipt", "entity_type": "fuel_log"},
            files={"upload": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        assert upload_response.status_code == 200
        uploaded = upload_response.json()
        assert uploaded["file_type"] == "receipt"
        assert uploaded["mime_type"] == "image/jpeg"
        assert uploaded["size_bytes"] == len(b"fake-image-bytes")
        assert uploaded["confirmed_at"] is not None
        upload_replay = await client.post(
            "/api/v1/files/upload",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "file:upload:receipt:001"},
            data={"file_type": "receipt", "entity_type": "fuel_log"},
            files={"upload": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        assert upload_replay.status_code == 200
        assert upload_replay.json()["id"] == uploaded["id"]

        get_response = await client.get(
            f"/api/v1/files/{uploaded['id']}",
            headers=auth_headers(tenant.id),
        )
        assert get_response.status_code == 200
        assert get_response.json()["id"] == uploaded["id"]

        other_tenant_response = await client.get(
            f"/api/v1/files/{uploaded['id']}",
            headers=auth_headers(other_tenant.id),
        )
        assert other_tenant_response.status_code == 404

    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(
            select(AuditLog.action).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_id == UUID(uploaded["id"]),
            )
        )
        assert set(audit_rows.scalars()) == {"file.uploaded"}


@pytest.mark.asyncio
async def test_presign_and_confirm_upload_create_file_metadata() -> None:
    tenant = await create_tenant()

    async with await create_api_client() as client:
        payload = {
            "entity_type": "delivery_proof",
            "file_type": "document",
            "original_name": "descarga.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 128,
            "sha256_hash": "a" * 64,
        }
        presign_response = await client.post(
            "/api/v1/files/presign",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "file:presign:descarga"},
            json=payload,
        )
        assert presign_response.status_code == 200
        presigned = presign_response.json()
        assert presigned["upload_url"].startswith("local://")
        presign_replay = await client.post(
            "/api/v1/files/presign",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "file:presign:descarga"},
            json=payload,
        )
        assert presign_replay.status_code == 200
        assert presign_replay.json()["file_id"] == presigned["file_id"]

        confirm_response = await client.post(
            "/api/v1/files/confirm",
            headers=auth_headers(tenant.id),
            json={"file_id": presigned["file_id"], "entity_type": "delivery_proof"},
        )
        assert confirm_response.status_code == 200
        confirmed = confirm_response.json()
        assert confirmed["id"] == presigned["file_id"]
        assert confirmed["confirmed_at"] is not None
        confirm_replay = await client.post(
            "/api/v1/files/confirm",
            headers=auth_headers(tenant.id),
            json={"file_id": presigned["file_id"], "entity_type": "delivery_proof"},
        )
        assert confirm_replay.status_code == 200
        assert confirm_replay.json()["confirmed_at"] == confirmed["confirmed_at"]

    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(
            select(AuditLog.action).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_id == UUID(presigned["file_id"]),
            )
        )
        assert set(audit_rows.scalars()) == {"file.presigned", "file.confirmed"}


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_mime_type() -> None:
    tenant = await create_tenant()
    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/files/upload",
            headers=auth_headers(tenant.id),
            data={"file_type": "receipt", "entity_type": "fuel_log"},
            files={"upload": ("payload.exe", b"not-an-image", "application/octet-stream")},
        )
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "unsupported_mime_type"


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file() -> None:
    tenant = await create_tenant()
    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/files/upload",
            headers=auth_headers(tenant.id),
            data={"file_type": "receipt", "entity_type": "fuel_log"},
            files={"upload": ("large.pdf", b"x" * (8 * 1024 * 1024 + 1), "application/pdf")},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "invalid_file_size"
