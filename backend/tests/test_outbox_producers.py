import ast
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.modules.alerts.models import Alert
from app.modules.audit.models import AuditLog
from app.modules.operational_exceptions.models import OperationalException
from app.modules.operational_exceptions.service import ensure_exception
from app.modules.outbox.models import OutboxEvent
from app.modules.tenants.models import Tenant


async def test_high_exception_persists_one_tenant_scoped_event(db, tenant_id) -> None:
    entity_id = uuid4()
    first = await ensure_exception(
        db,
        tenant_id,
        entity_type="vehicle",
        entity_id=entity_id,
        exception_type="vehicle_breakdown",
        severity="high",
        title="Avaria imobilizante",
        message="A viatura não pode continuar a viagem.",
    )
    replay = await ensure_exception(
        db,
        tenant_id,
        entity_type="vehicle",
        entity_id=entity_id,
        exception_type="vehicle_breakdown",
        severity="high",
        title="Avaria imobilizante",
        message="A viatura não pode continuar a viagem.",
    )
    await db.commit()

    events = (
        (
            await db.execute(
                select(OutboxEvent).where(
                    OutboxEvent.tenant_id == tenant_id,
                    OutboxEvent.aggregate_id == first.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert replay.id == first.id
    assert len(events) == 1
    assert events[0].id == first.id
    assert events[0].aggregate_type == "operational_exception"
    assert events[0].event_type == "vehicle.breakdown"
    assert events[0].status == "pending"
    assert isinstance(events[0].payload["occurred_at"], str)
    assert events[0].payload["idempotency_key"] == f"rotas:exception:{first.id}:{tenant_id}"


async def test_low_exception_does_not_create_external_event(db, tenant_id) -> None:
    item = await ensure_exception(
        db,
        tenant_id,
        entity_type="vehicle",
        entity_id=uuid4(),
        exception_type="inspection_note",
        severity="low",
        title="Nota de inspeção",
        message="Acompanhar na próxima revisão.",
    )
    await db.commit()

    assert (
        await db.scalar(
            select(func.count(OutboxEvent.id)).where(
                OutboxEvent.tenant_id == tenant_id,
                OutboxEvent.aggregate_id == item.id,
            )
        )
        == 0
    )


async def test_exception_alert_audit_and_outbox_roll_back_together(db, tenant_id) -> None:
    entity_id = uuid4()
    item = await ensure_exception(
        db,
        tenant_id,
        entity_type="cargo",
        entity_id=entity_id,
        exception_type="cargo_damage",
        severity="critical",
        title="Carga danificada",
        message="A carga requer contenção imediata.",
    )
    item_id = item.id
    await db.rollback()

    assert await db.get(OperationalException, item_id) is None
    assert await db.get(OutboxEvent, item_id) is None
    assert (
        await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.tenant_id == tenant_id,
                Alert.request_reference == f"exception:{item_id}",
            )
        )
        == 0
    )
    assert (
        await db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.entity_id.in_([entity_id, item_id]),
            )
        )
        == 0
    )


async def test_producer_events_remain_isolated_by_tenant(db, tenant_id) -> None:
    other_tenant = Tenant(name="Outbox tenant B", slug=f"outbox-b-{uuid4().hex[:8]}")
    db.add(other_tenant)
    await db.flush()
    shared_entity_id = uuid4()

    first = await ensure_exception(
        db,
        tenant_id,
        entity_type="trip",
        entity_id=shared_entity_id,
        exception_type="trip_incident",
        severity="high",
        title="Incidente A",
        message="Incidente do tenant A.",
    )
    second = await ensure_exception(
        db,
        other_tenant.id,
        entity_type="trip",
        entity_id=shared_entity_id,
        exception_type="trip_incident",
        severity="high",
        title="Incidente B",
        message="Incidente do tenant B.",
    )
    await db.commit()

    events = (
        (
            await db.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_([first.id, second.id]))
            )
        )
        .scalars()
        .all()
    )
    assert {(event.id, event.tenant_id) for event in events} == {
        (first.id, tenant_id),
        (second.id, other_tenant.id),
    }
    for event in events:
        assert str(event.tenant_id) in event.payload["idempotency_key"]


def test_backend_has_no_fire_and_forget_integration_producer() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    violations: list[str] = []
    direct_governance_imports: list[str] = []

    for source_path in app_root.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "create_task")
                or (isinstance(node.func, ast.Name) and node.func.id == "create_task")
            ):
                violations.append(f"{source_path.relative_to(app_root)}:{node.lineno}")
            if isinstance(node, ast.ImportFrom) and node.module == "app.modules.governance.client":
                direct_governance_imports.append(
                    f"{source_path.relative_to(app_root)}:{node.lineno}"
                )

    assert violations == []
    assert direct_governance_imports == []
