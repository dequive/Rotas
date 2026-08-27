"""Database-level tenant isolation for the critical Workshop data path."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.modules.clients.models import Client
from app.modules.files.models import File as StoredFile
from app.modules.outbox.models import OutboxEvent
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder

CRITICAL_WORKSHOP_TABLES = (
    "clients",
    "vehicles",
    "work_orders",
    "files",
    "outbox_events",
)


async def _set_restricted_tenant(db: AsyncSession, tenant_id: UUID | None) -> None:
    await db.execute(text("SET LOCAL ROLE rotas_app"))
    if tenant_id is not None:
        await db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )


@pytest.fixture
async def workshop_rls_seed():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant_a = Tenant(name=f"Workshop RLS A {suffix}", slug=f"workshop-rls-a-{suffix}")
        tenant_b = Tenant(name=f"Workshop RLS B {suffix}", slug=f"workshop-rls-b-{suffix}")
        db.add_all([tenant_a, tenant_b])
        await db.flush()

        client_a = Client(
            tenant_id=tenant_a.id,
            trading_name="Cliente privado A",
            nuit=f"1{suffix[:8]}",
            client_type="organization",
        )
        client_b = Client(
            tenant_id=tenant_b.id,
            trading_name="Cliente privado B",
            nuit=f"2{suffix[:8]}",
            client_type="organization",
        )
        vehicle_a = Vehicle(tenant_id=tenant_a.id, plate=f"RLA-{suffix[:5]}")
        vehicle_b = Vehicle(tenant_id=tenant_b.id, plate=f"RLB-{suffix[:5]}")
        db.add_all([client_a, client_b, vehicle_a, vehicle_b])
        await db.flush()

        work_order_a = WorkOrder(
            tenant_id=tenant_a.id,
            vehicle_id=vehicle_a.id,
            work_order_number=f"OS-RLS-A-{suffix}",
            planned_work="Intervenção privada A",
            status="draft",
        )
        work_order_b = WorkOrder(
            tenant_id=tenant_b.id,
            vehicle_id=vehicle_b.id,
            work_order_number=f"OS-RLS-B-{suffix}",
            planned_work="Intervenção privada B",
            status="draft",
        )
        file_a = StoredFile(
            tenant_id=tenant_a.id,
            entity_type="work_order",
            entity_id=work_order_a.id,
            file_type="workshop_evidence",
            original_name="tenant-a.jpg",
            storage_key=f"rls/{suffix}/tenant-a.jpg",
            mime_type="image/jpeg",
            size_bytes=10,
            sha256_hash="a" * 64,
        )
        file_b = StoredFile(
            tenant_id=tenant_b.id,
            entity_type="work_order",
            entity_id=work_order_b.id,
            file_type="workshop_evidence",
            original_name="tenant-b.jpg",
            storage_key=f"rls/{suffix}/tenant-b.jpg",
            mime_type="image/jpeg",
            size_bytes=10,
            sha256_hash="b" * 64,
        )
        event_a = OutboxEvent(
            tenant_id=tenant_a.id,
            aggregate_type="work_order",
            aggregate_id=work_order_a.id,
            event_type="workshop.private.a",
            payload={"secret": "tenant-a"},
        )
        event_b = OutboxEvent(
            tenant_id=tenant_b.id,
            aggregate_type="work_order",
            aggregate_id=work_order_b.id,
            event_type="workshop.private.b",
            payload={"secret": "tenant-b"},
        )
        db.add_all([work_order_a, work_order_b, file_a, file_b, event_a, event_b])
        await db.commit()

        return {
            "tenant_a": tenant_a.id,
            "tenant_b": tenant_b.id,
            "client_a": client_a.id,
            "client_b": client_b.id,
            "vehicle_a": vehicle_a.id,
            "work_order_a": work_order_a.id,
            "file_a": file_a.id,
        }


async def test_restricted_role_only_reads_current_tenant(workshop_rls_seed):
    tenant_a = workshop_rls_seed["tenant_a"]
    tenant_b = workshop_rls_seed["tenant_b"]

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_restricted_tenant(db, tenant_b)
            assert await db.scalar(text("SELECT current_user")) == "rotas_app"
            assert (
                await db.scalar(
                    text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
                is False
            )

            for table_name in CRITICAL_WORKSHOP_TABLES:
                visible_tenants = {
                    row.tenant_id
                    for row in (
                        await db.execute(text(f"SELECT tenant_id FROM {table_name}"))
                    ).all()
                }
                assert tenant_a not in visible_tenants
                assert visible_tenants <= {tenant_b}


async def test_restricted_role_without_context_reads_no_tenant_rows(workshop_rls_seed):
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_restricted_tenant(db, None)
            for table_name in CRITICAL_WORKSHOP_TABLES:
                count = await db.scalar(text(f"SELECT count(*) FROM {table_name}"))
                assert count == 0


async def test_restricted_role_cannot_mutate_hidden_or_change_tenant(workshop_rls_seed):
    tenant_a = workshop_rls_seed["tenant_a"]
    tenant_b = workshop_rls_seed["tenant_b"]
    client_a = workshop_rls_seed["client_a"]
    client_b = workshop_rls_seed["client_b"]
    work_order_a = workshop_rls_seed["work_order_a"]

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_restricted_tenant(db, tenant_b)
            hidden_update = await db.execute(
                text(
                    "UPDATE work_orders SET diagnosis = 'cross-tenant mutation' "
                    "WHERE id = :work_order_id"
                ),
                {"work_order_id": work_order_a},
            )
            assert getattr(hidden_update, "rowcount", None) == 0

    with pytest.raises(DBAPIError, match="row-level security"):
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await _set_restricted_tenant(db, tenant_b)
                await db.execute(
                    text("UPDATE clients SET tenant_id = :tenant_a WHERE id = :client_b"),
                    {"tenant_a": tenant_a, "client_b": client_b},
                )

    async with AsyncSessionLocal() as db:
        assert await db.scalar(
            text("SELECT tenant_id FROM clients WHERE id = :client_a"),
            {"client_a": client_a},
        ) == tenant_a
        assert await db.scalar(
            text("SELECT tenant_id FROM clients WHERE id = :client_b"),
            {"client_b": client_b},
        ) == tenant_b


async def test_critical_workshop_policies_have_read_and_write_guards():
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT tablename, roles, qual, with_check "
                    "FROM pg_policies "
                    "WHERE schemaname = 'public' "
                    "AND tablename = ANY(:table_names) "
                    "AND policyname = 'tenant_isolation'"
                ),
                {"table_names": list(CRITICAL_WORKSHOP_TABLES)},
            )
        ).mappings()
        policies = {row["tablename"]: row for row in rows}

    assert set(policies) == set(CRITICAL_WORKSHOP_TABLES)
    for policy in policies.values():
        assert policy["roles"] == ["rotas_app"]
        assert "app.tenant_id" in policy["qual"]
        assert "app.tenant_id" in policy["with_check"]


async def test_api_rejects_cross_tenant_relationship_and_file_access(
    workshop_rls_seed, async_client
):
    headers_b = {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(workshop_rls_seed["tenant_b"]),
    }

    cross_tenant_work_order = await async_client.post(
        "/api/v1/workshop/work-orders",
        headers=headers_b,
        json={
            "vehicle_id": str(workshop_rls_seed["vehicle_a"]),
            "planned_work": "Referência cruzada proibida",
        },
    )
    assert cross_tenant_work_order.status_code == 404

    cross_tenant_file = await async_client.get(
        f"/api/v1/files/{workshop_rls_seed['file_a']}",
        headers=headers_b,
    )
    assert cross_tenant_file.status_code == 404
