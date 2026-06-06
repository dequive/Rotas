from uuid import uuid4

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


async def create_tenant(*, max_users: int = 3) -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Tenant Access Setup {suffix}",
            slug=f"access-setup-{suffix}",
            max_users=max_users,
        )
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
async def test_tenant_me_and_user_management_are_tenant_scoped() -> None:
    tenant = await create_tenant(max_users=1)
    other_tenant = await create_tenant()

    async with await create_api_client() as client:
        tenant_response = await client.get("/api/v1/tenants/me", headers=auth_headers(tenant.id))
        assert tenant_response.status_code == 200
        assert tenant_response.json()["id"] == str(tenant.id)
        assert tenant_response.json()["compliance_policy"] is None

        empty_despacho_table = await client.get(
            "/api/v1/tenants/me/driver-despacho-table",
            headers=auth_headers(tenant.id),
        )
        assert empty_despacho_table.status_code == 200
        assert empty_despacho_table.json() == {"configured": False, "table": None}

        policy_response = await client.patch(
            "/api/v1/tenants/me",
            headers=auth_headers(tenant.id),
            json={
                "compliance_policy": {
                    "vehicle_required_documents": ["insurance", "inspection"],
                    "driver_required_documents": ["driving_license", "inatter_license"],
                    "cargo_required_documents_by_type": {
                        "Carga contratual": ["load_permit", "transport_document:client_waybill"]
                    },
                    "trip_required_stops_by_cargo_type": {
                        "Carga contratual": ["weighbridge", "checkpoint"]
                    },
                    "driver_travel_allowance_policy": {
                        "enabled": True,
                        "table_name": "Tabela de despacho Centro 2026",
                        "table_reference": "TD-CENTRO-2026",
                        "currency": "MZN",
                        "min_long_course_km": 100,
                        "tiers": [
                            {
                                "min_km": 100,
                                "max_km": 300,
                                "amount": 750,
                                "label": "Centro curto",
                            }
                        ],
                    },
                }
            },
        )
        assert policy_response.status_code == 200
        assert policy_response.json()["compliance_policy"]["vehicle_required_documents"] == [
            "insurance",
            "inspection",
        ]
        assert policy_response.json()["compliance_policy"]["cargo_required_documents_by_type"][
            "Carga contratual"
        ] == ["load_permit", "transport_document:client_waybill"]
        assert policy_response.json()["compliance_policy"]["trip_required_stops_by_cargo_type"][
            "Carga contratual"
        ] == ["weighbridge", "checkpoint"]
        assert policy_response.json()["compliance_policy"]["driver_travel_allowance_policy"][
            "table_reference"
        ] == "TD-CENTRO-2026"
        assert policy_response.json()["compliance_policy"]["driver_travel_allowance_policy"][
            "tiers"
        ][0]["amount"] == 750

        invalid_policy_response = await client.patch(
            "/api/v1/tenants/me",
            headers=auth_headers(tenant.id),
            json={"compliance_policy": {"cargo_required_documents_by_type": ["load_permit"]}},
        )
        assert invalid_policy_response.status_code == 422
        assert invalid_policy_response.json()["error"]["code"] == "invalid_compliance_policy"

        invalid_allowance_response = await client.patch(
            "/api/v1/tenants/me",
            headers=auth_headers(tenant.id),
            json={
                "compliance_policy": {
                    "driver_travel_allowance_policy": {"tiers": [{"min_km": "100"}]}
                }
            },
        )
        assert invalid_allowance_response.status_code == 422
        assert invalid_allowance_response.json()["error"]["code"] == "invalid_compliance_policy"

        invalid_allowance_table_response = await client.patch(
            "/api/v1/tenants/me",
            headers=auth_headers(tenant.id),
            json={
                "compliance_policy": {
                    "driver_travel_allowance_policy": {
                        "currency": "METICAL",
                        "tiers": [{"min_km": 300, "max_km": 100, "amount": 750}],
                    }
                }
            },
        )
        assert invalid_allowance_table_response.status_code == 422
        assert (
            invalid_allowance_table_response.json()["error"]["code"]
            == "invalid_compliance_policy"
        )

        manual_despacho_table = await client.put(
            "/api/v1/tenants/me/driver-despacho-table",
            headers=auth_headers(tenant.id),
            json={
                "enabled": True,
                "table_name": "Tabela manual Norte 2026",
                "table_reference": "TD-NORTE-2026",
                "currency": "mzn",
                "effective_from": "2026-02-01",
                "min_long_course_km": 120,
                "tiers": [
                    {
                        "min_km": 120,
                        "max_km": 350,
                        "amount": 900,
                        "label": "Norte medio",
                        "code": "N-MED",
                    },
                    {
                        "min_km": 350,
                        "amount": 1600,
                        "label": "Norte longo",
                        "code": "N-LONG",
                    },
                ],
            },
        )
        assert manual_despacho_table.status_code == 200
        table_payload = manual_despacho_table.json()
        assert table_payload["configured"] is True
        assert table_payload["table"]["entry_mode"] == "manual"
        assert table_payload["table"]["currency"] == "MZN"
        assert table_payload["table"]["tiers"][1]["code"] == "N-LONG"

        confirmed_despacho_table = await client.get(
            "/api/v1/tenants/me/driver-despacho-table",
            headers=auth_headers(tenant.id),
        )
        assert confirmed_despacho_table.status_code == 200
        assert confirmed_despacho_table.json()["table"]["table_reference"] == "TD-NORTE-2026"

        create_response = await client.post(
            "/api/v1/users",
            headers=auth_headers(tenant.id),
            json={
                "email": "  OWNER@EXAMPLE.TEST ",
                "password": "secure-password",
                "full_name": "Owner One",
                "role": "owner",
            },
        )
        assert create_response.status_code == 200
        user = create_response.json()
        assert user["email"] == "owner@example.test"
        assert "password_hash" not in user

        duplicate_response = await client.post(
            "/api/v1/users",
            headers=auth_headers(tenant.id),
            json={
                "email": "owner@example.test",
                "password": "secure-password",
                "full_name": "Duplicate",
            },
        )
        assert duplicate_response.status_code == 409

        limit_response = await client.post(
            "/api/v1/users",
            headers=auth_headers(tenant.id),
            json={
                "email": "second@example.test",
                "password": "secure-password",
                "full_name": "Second",
            },
        )
        assert limit_response.status_code == 403
        assert "upgrade_url" in limit_response.json().get("details", {})

        other_tenant_response = await client.post(
            "/api/v1/users",
            headers=auth_headers(other_tenant.id),
            json={
                "email": "owner@example.test",
                "password": "secure-password",
                "full_name": "Other Tenant Owner",
            },
        )
        assert other_tenant_response.status_code == 200

        patch_response = await client.patch(
            f"/api/v1/users/{user['id']}",
            headers=auth_headers(tenant.id),
            json={"full_name": "Owner Updated", "is_active": False},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["full_name"] == "Owner Updated"
        assert patch_response.json()["is_active"] is False

        list_response = await client.get("/api/v1/users", headers=auth_headers(tenant.id))
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [user["id"]]

    async with AsyncSessionLocal() as db:
        audit_actions = await db.execute(
            select(AuditLog.action).where(AuditLog.tenant_id == tenant.id)
        )
        actions = set(audit_actions.scalars())
        assert "tenant.updated" in actions
        assert "tenant.driver_despacho_table.updated" in actions


@pytest.mark.asyncio
async def test_alert_creation_and_status_updates_are_idempotent_and_audited() -> None:
    tenant = await create_tenant()
    payload = {
        "request_reference": "tower:vehicle:abc:maintenance",
        "alert_type": "vehicle_maintenance",
        "priority": "high",
        "entity_type": "vehicle",
        "title": "Vehicle requires maintenance",
    }

    async with await create_api_client() as client:
        create_response = await client.post(
            "/api/v1/alerts",
            headers=auth_headers(tenant.id),
            json=payload,
        )
        assert create_response.status_code == 200
        alert = create_response.json()

        replay_response = await client.post(
            "/api/v1/alerts",
            headers=auth_headers(tenant.id),
            json=payload,
        )
        assert replay_response.status_code == 200
        assert replay_response.json()["id"] == alert["id"]

        conflict_response = await client.post(
            "/api/v1/alerts",
            headers=auth_headers(tenant.id),
            json={**payload, "title": "Changed title"},
        )
        assert conflict_response.status_code == 409

        read_response = await client.patch(
            f"/api/v1/alerts/{alert['id']}/status",
            headers=auth_headers(tenant.id),
            json={"status": "read"},
        )
        assert read_response.status_code == 200
        assert read_response.json()["read_at"] is not None

        replay_read_response = await client.patch(
            f"/api/v1/alerts/{alert['id']}/status",
            headers=auth_headers(tenant.id),
            json={"status": "read"},
        )
        assert replay_read_response.status_code == 200
        assert replay_read_response.json()["read_at"] == read_response.json()["read_at"]

        list_response = await client.get(
            "/api/v1/alerts",
            headers=auth_headers(tenant.id),
            params={"status": "read"},
        )
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [alert["id"]]

    async with AsyncSessionLocal() as db:
        actions = list(
            await db.scalars(
                select(AuditLog.action)
                .where(AuditLog.tenant_id == tenant.id)
                .order_by(AuditLog.created_at.asc())
            )
        )
        assert actions == ["alert.created", "alert.status_updated"]
