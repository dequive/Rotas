"""Per-entity replay and conflict proof for the offline sync batch.

This is the promise the product exists for: a driver completes a whole trip
with no signal, and everything reaches the manager intact when the network
comes back. The driver's phone retries the batch — on a flaky Mozambican
mobile link it will retry, repeatedly, and often after the server already
committed the write but before the response arrived.

Two failures matter, and neither is visible from the happy path:

1. A retry that **duplicates** — a second fuel log is a phantom cost on the
   vehicle, a second delivery proof is a delivery that never happened, a
   second trip cost inflates the margin report the manager bills from.
2. A retry that **silently returns the first answer for different data** — the
   driver corrects the litres, the phone reuses the key, and the correction is
   swallowed while the UI shows success.

The suite proved both for one entity type. The sync dispatcher handles nine on
create, so the other eight were only covered by inspection. This module proves
each of them separately, because they take different code paths through
different services.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.cargo.models import (
    CargoManifest,
    DeliveryProof,
    LoadPermit,
    TransportDocument,
)
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelLog
from app.modules.tenants.models import Tenant
from app.modules.trips import service as trip_service
from app.modules.trips.models import Trip, TripCost, TripStop
from app.modules.trips.schemas import TripCreate
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def _seed() -> dict:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"SyncMatrix {suffix}", slug=f"syncm-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"MZ-SM-{suffix[:4].upper()}",
            fuel_type="gasoleo",
            status="active",
        )
        driver = Driver(tenant_id=tenant.id, full_name=f"Motorista {suffix}", status="active")
        db.add_all([vehicle, driver])
        await db.flush()

        template = ChecklistTemplate(
            tenant_id=tenant.id,
            name="Pre-Trip Check",
            type="pre_trip",
            items=[{"id": "tyres", "label": "Pneus", "type": "ok_fail"}],
        )
        db.add(template)
        await db.flush()

        trip = await trip_service.create_trip(
            db,
            tenant.id,
            TripCreate(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                origin="Maputo",
                destination="Beira",
                cargo_type="Carga geral",
            ),
        )
        await db.commit()

        return {
            "tenant_id": tenant.id,
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "template_id": str(template.id),
            "trip_id": str(trip["id"]),
        }


class SyncCase:
    """One sync entity type, with a payload and a meaningfully different one.

    `mutated` always changes a field the driver could plausibly correct after a
    failed send — litres, weight, an amount — not a cosmetic field, so a
    swallowed correction would be a real data loss.
    """

    def __init__(self, entity_type: str, model: Any, payload, mutated) -> None:
        self.entity_type = entity_type
        self.model = model
        self._payload = payload
        self._mutated = mutated

    def payload(self, ids: dict) -> dict:
        return self._payload(ids)

    def mutated(self, ids: dict) -> dict:
        return self._mutated(ids)

    def __repr__(self) -> str:  # pragma: no cover - pytest id only
        return self.entity_type


CASES: list[SyncCase] = [
    SyncCase(
        "checklist",
        Checklist,
        lambda ids: {
            "vehicleId": ids["vehicle_id"],
            "driverId": ids["driver_id"],
            "templateId": ids["template_id"],
            "type": "pre_trip",
            "responses": {"tyres": "ok"},
            "complete": True,
        },
        lambda ids: {
            "vehicleId": ids["vehicle_id"],
            "driverId": ids["driver_id"],
            "templateId": ids["template_id"],
            "type": "pre_trip",
            "responses": {"tyres": "fail"},
            "complete": True,
        },
    ),
    SyncCase(
        "fuel_log",
        FuelLog,
        lambda ids: {
            "vehicleId": ids["vehicle_id"],
            "driverId": ids["driver_id"],
            "fuelDate": _now(),
            "fuelType": "gasoleo",
            "liters": 80.0,
            "totalCost": 7200.0,
            "kmAtRefuel": 42000,
            "stationName": "Galp Inchope",
        },
        lambda ids: {
            "vehicleId": ids["vehicle_id"],
            "driverId": ids["driver_id"],
            "fuelDate": _now(),
            "fuelType": "gasoleo",
            "liters": 95.0,
            "totalCost": 8550.0,
            "kmAtRefuel": 42000,
            "stationName": "Galp Inchope",
        },
    ),
    SyncCase(
        "trip_stop",
        TripStop,
        lambda ids: {
            "tripId": ids["trip_id"],
            "stopType": "rest",
            "address": "Posto Inchope",
            "notes": "Paragem obrigatoria — controlo policial",
        },
        lambda ids: {
            "tripId": ids["trip_id"],
            "stopType": "refuel",
            "address": "Posto Inchope",
            "notes": "Paragem obrigatoria — controlo policial",
        },
    ),
    SyncCase(
        "trip_cost",
        TripCost,
        lambda ids: {
            "tripId": ids["trip_id"],
            "costType": "toll",
            "amount": 350.0,
            "currency": "MZN",
            "incurredAt": _now(),
            "description": "Portagem EN1",
            "requestReference": "toll-en1-001",
        },
        lambda ids: {
            "tripId": ids["trip_id"],
            "costType": "toll",
            "amount": 750.0,
            "currency": "MZN",
            "incurredAt": _now(),
            "description": "Portagem EN1",
            "requestReference": "toll-en1-001",
        },
    ),
    SyncCase(
        "load_permit",
        LoadPermit,
        lambda ids: {
            "tripId": ids["trip_id"],
            "clientName": "Cimentos de Mocambique",
            "origin": "Matola",
            "destination": "Beira",
            "loadState": "loaded",
        },
        lambda ids: {
            "tripId": ids["trip_id"],
            "clientName": "Cimentos de Mocambique",
            "origin": "Matola",
            "destination": "Nampula",
            "loadState": "loaded",
        },
    ),
    SyncCase(
        "cargo_manifest",
        CargoManifest,
        lambda ids: {
            "tripId": ids["trip_id"],
            "cargoDescription": "Sacos de cimento 50kg",
            "cargoType": "bulk",
            "grossWeight": 20000.0,
            "packageCount": 400,
        },
        lambda ids: {
            "tripId": ids["trip_id"],
            "cargoDescription": "Sacos de cimento 50kg",
            "cargoType": "bulk",
            "grossWeight": 26000.0,
            "packageCount": 520,
        },
    ),
    SyncCase(
        "transport_document",
        TransportDocument,
        lambda ids: {
            "tripId": ids["trip_id"],
            "documentType": "guia_de_transporte",
            "documentNumber": "GT-000123",
            "issuedAt": _now(),
        },
        lambda ids: {
            "tripId": ids["trip_id"],
            "documentType": "guia_de_transporte",
            "documentNumber": "GT-000999",
            "issuedAt": _now(),
        },
    ),
    SyncCase(
        "delivery_proof",
        DeliveryProof,
        lambda ids: {
            "tripId": ids["trip_id"],
            "proofType": "client_discharge_note",
            "clientType": "company",
            "receiverName": "Armazem Beira",
            "deliveredAt": _now(),
            "cargoCondition": "intact",
            "quantityDelivered": 400.0,
        },
        lambda ids: {
            "tripId": ids["trip_id"],
            "proofType": "client_discharge_note",
            "clientType": "company",
            "receiverName": "Armazem Beira",
            "deliveredAt": _now(),
            "cargoCondition": "damaged",
            "quantityDelivered": 380.0,
        },
    ),
]


def _operation(case: SyncCase, ids: dict, key: str, payload: dict) -> dict:
    return {
        "local_id": f"local_{case.entity_type}_{key[:8]}",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": case.entity_type,
        "payload": payload,
    }


async def _post_batch(tenant_id, device_id: str, operations: list[dict]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/api/v1/sync/batch",
            headers=_headers(tenant_id),
            json={"device_id": device_id, "operations": operations},
        )


async def _count(model: Any, tenant_id) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count(model.id)).where(model.tenant_id == tenant_id))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.entity_type)
async def test_retrying_the_batch_does_not_duplicate(case: SyncCase) -> None:
    ids = await _seed()
    tenant_id = ids["tenant_id"]
    device_id = f"phone-{uuid4().hex[:8]}"
    key = str(uuid4())
    payload = case.payload(ids)

    before = await _count(case.model, tenant_id)

    first = await _post_batch(tenant_id, device_id, [_operation(case, ids, key, payload)])
    assert first.status_code == 200, first.text
    first_result = first.json()["results"][0]
    assert first_result["status"] == "processed", first_result

    after_first = await _count(case.model, tenant_id)
    assert after_first == before + 1, f"{case.entity_type}: a primeira escrita nao aconteceu"

    # The phone never saw the response and sends the same batch again.
    replay = await _post_batch(tenant_id, device_id, [_operation(case, ids, key, payload)])
    assert replay.status_code == 200, replay.text
    replay_result = replay.json()["results"][0]

    assert replay_result["server_id"] == first_result["server_id"], (
        f"{case.entity_type}: a repeticao devolveu outra entidade "
        f"({replay_result['server_id']} != {first_result['server_id']})"
    )
    assert await _count(case.model, tenant_id) == after_first, (
        f"{case.entity_type}: a repeticao do lote duplicou o registo"
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.entity_type)
async def test_corrected_payload_under_the_same_key_is_flagged_not_swallowed(
    case: SyncCase,
) -> None:
    """The driver corrects the data; the phone reuses the key.

    Returning the first response here would discard the correction while the
    app showed success — the quiet form of data loss this whole sync design
    exists to prevent. The batch must come back as `conflict`.
    """
    ids = await _seed()
    tenant_id = ids["tenant_id"]
    device_id = f"phone-{uuid4().hex[:8]}"
    key = str(uuid4())

    first = await _post_batch(tenant_id, device_id, [_operation(case, ids, key, case.payload(ids))])
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "processed"

    after_first = await _count(case.model, tenant_id)

    conflict = await _post_batch(tenant_id, device_id, [_operation(case, ids, key, case.mutated(ids))])
    assert conflict.status_code == 200, conflict.text
    result = conflict.json()["results"][0]

    assert result["status"] == "conflict", (
        f"{case.entity_type}: payload corrigido devolveu status={result['status']!r}. "
        f"A correccao do motorista foi engolida."
    )
    assert result["error_code"] == "idempotency_key_reused", result
    assert await _count(case.model, tenant_id) == after_first, f"{case.entity_type}: o conflito escreveu na base"


async def test_one_conflicting_operation_does_not_discard_the_rest_of_the_batch() -> None:
    """A batch is not all-or-nothing, and must not be.

    A driver comes back online with a queue built over hours. If one stale
    operation poisoned the whole batch, everything recorded that day would be
    stuck behind it — the opposite of the guarantee. Each operation carries its
    own result.
    """
    ids = await _seed()
    tenant_id = ids["tenant_id"]
    device_id = f"phone-{uuid4().hex[:8]}"

    fuel_case = next(c for c in CASES if c.entity_type == "fuel_log")
    stop_case = next(c for c in CASES if c.entity_type == "trip_stop")

    burnt_key = str(uuid4())
    seeded = await _post_batch(tenant_id, device_id, [_operation(fuel_case, ids, burnt_key, fuel_case.payload(ids))])
    assert seeded.json()["results"][0]["status"] == "processed"

    stops_before = await _count(TripStop, tenant_id)

    mixed = await _post_batch(
        tenant_id,
        device_id,
        [
            _operation(fuel_case, ids, burnt_key, fuel_case.mutated(ids)),
            _operation(stop_case, ids, str(uuid4()), stop_case.payload(ids)),
        ],
    )
    assert mixed.status_code == 200, mixed.text
    results = {r["entity_type"]: r for r in mixed.json()["results"]}

    assert results["fuel_log"]["status"] == "conflict", results["fuel_log"]
    assert results["trip_stop"]["status"] == "processed", (
        f"uma operacao em conflito arrastou consigo o resto do lote: {results['trip_stop']}"
    )
    assert await _count(TripStop, tenant_id) == stops_before + 1, (
        "a paragem valida nao foi gravada por causa do conflito na outra operacao"
    )


async def test_the_same_key_from_two_tenants_does_not_collide() -> None:
    """Idempotency keys are client-generated; two tenants can pick the same one."""
    first_ids = await _seed()
    second_ids = await _seed()
    case = next(c for c in CASES if c.entity_type == "fuel_log")
    shared_key = str(uuid4())

    first = await _post_batch(
        first_ids["tenant_id"],
        f"phone-{uuid4().hex[:8]}",
        [_operation(case, first_ids, shared_key, case.payload(first_ids))],
    )
    assert first.json()["results"][0]["status"] == "processed", first.text

    second = await _post_batch(
        second_ids["tenant_id"],
        f"phone-{uuid4().hex[:8]}",
        [_operation(case, second_ids, shared_key, case.payload(second_ids))],
    )
    assert second.status_code == 200, second.text
    result = second.json()["results"][0]

    assert result["status"] == "processed", f"a chave gasta noutro tenant bloqueou esta escrita: {result}"
    assert result["server_id"] != first.json()["results"][0]["server_id"]
    assert await _count(FuelLog, second_ids["tenant_id"]) == 1


async def test_replayed_trip_creation_keeps_a_single_trip() -> None:
    """`trip` is the ninth create type and is seeded rather than posted, so it
    gets its own case: the trip is the row every other operation hangs off."""
    ids = await _seed()
    tenant_id = ids["tenant_id"]
    device_id = f"phone-{uuid4().hex[:8]}"
    key = str(uuid4())
    payload = {
        "vehicleId": ids["vehicle_id"],
        "driverId": ids["driver_id"],
        "origin": "Maputo",
        "destination": "Xai-Xai",
        "cargoType": "Carga geral",
    }
    operation = {
        "local_id": "local_trip_001",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": "trip",
        "payload": payload,
    }

    before = await _count(Trip, tenant_id)

    first = await _post_batch(tenant_id, device_id, [operation])
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "processed", first.text
    assert await _count(Trip, tenant_id) == before + 1

    replay = await _post_batch(tenant_id, device_id, [operation])
    assert replay.json()["results"][0]["server_id"] == first.json()["results"][0]["server_id"]
    assert await _count(Trip, tenant_id) == before + 1, "a repeticao criou uma segunda viagem"


async def test_one_invalid_operation_does_not_poison_the_whole_batch() -> None:
    """A malformed operation must fail alone, not take the batch with it.

    The driver's queue is built offline over hours. If one operation the server
    cannot validate — a field the app forgot to send, a schema that moved on
    without the installed client — aborted the request, every record captured
    that day would be stuck behind it, retried forever, and the guarantee the
    product is sold on would be false in exactly the situation it matters.
    """
    ids = await _seed()
    tenant_id = ids["tenant_id"]
    device_id = f"phone-{uuid4().hex[:8]}"

    stop_case = next(c for c in CASES if c.entity_type == "trip_stop")
    stops_before = await _count(TripStop, tenant_id)

    response = await _post_batch(
        tenant_id,
        device_id,
        [
            {
                "local_id": "local_fuel_broken",
                "idempotency_key": str(uuid4()),
                "operation": "create",
                "entity_type": "fuel_log",
                # No vehicleId: a queue entry written by a build whose shape has
                # since moved on, which is how this arrives in practice.
                "payload": {
                    "driverId": ids["driver_id"],
                    "fuelDate": _now(),
                    "liters": 80.0,
                },
            },
            _operation(stop_case, ids, str(uuid4()), stop_case.payload(ids)),
        ],
    )

    assert response.status_code == 200, (
        f"uma operacao invalida derrubou o lote inteiro com {response.status_code}. "
        f"Tudo o que o motorista registou offline fica preso atras dela."
    )
    results = {r["entity_type"]: r for r in response.json()["results"]}

    assert results["fuel_log"]["status"] == "failed", results["fuel_log"]
    assert results["fuel_log"]["error_code"] == "payload_validation_failed"
    assert results["trip_stop"]["status"] == "processed", (
        f"a operacao valida foi descartada por causa da invalida: {results['trip_stop']}"
    )
    assert await _count(TripStop, tenant_id) == stops_before + 1


# ── Update operations ─────────────────────────────────────────────────────────
# The update dispatcher already reports failure per operation, but nothing
# proved that a retried update applies once, that a corrected payload under a
# burnt key is refused, or that a rejected update leaves the row untouched.


async def _create_fuel_log(ids: dict, device_id: str) -> str:
    case = next(c for c in CASES if c.entity_type == "fuel_log")
    response = await _post_batch(ids["tenant_id"], device_id, [_operation(case, ids, str(uuid4()), case.payload(ids))])
    result = response.json()["results"][0]
    assert result["status"] == "processed", result
    return result["server_id"]


def _update_operation(server_id: str, key: str, liters: float) -> dict:
    return {
        "local_id": f"local_update_{key[:8]}",
        "idempotency_key": key,
        "operation": "update",
        "entity_type": "fuel_log",
        "payload": {"serverId": server_id, "liters": liters, "totalCost": liters * 90.0},
    }


async def _liters_of(tenant_id, fuel_log_id: str) -> float:
    async with AsyncSessionLocal() as db:
        value = await db.scalar(select(FuelLog.liters).where(FuelLog.id == UUID(fuel_log_id)))
        return float(value)


async def test_replayed_update_applies_once() -> None:
    ids = await _seed()
    device_id = f"phone-{uuid4().hex[:8]}"
    fuel_log_id = await _create_fuel_log(ids, device_id)
    key = str(uuid4())

    first = await _post_batch(ids["tenant_id"], device_id, [_update_operation(fuel_log_id, key, 91.0)])
    assert first.json()["results"][0]["status"] == "processed", first.text
    assert await _liters_of(ids["tenant_id"], fuel_log_id) == 91.0

    replay = await _post_batch(ids["tenant_id"], device_id, [_update_operation(fuel_log_id, key, 91.0)])
    assert replay.status_code == 200, replay.text
    assert await _liters_of(ids["tenant_id"], fuel_log_id) == 91.0


async def test_corrected_update_under_a_burnt_key_is_refused() -> None:
    """The driver fixes the litres twice; the second correction must not vanish."""
    ids = await _seed()
    device_id = f"phone-{uuid4().hex[:8]}"
    fuel_log_id = await _create_fuel_log(ids, device_id)
    key = str(uuid4())

    await _post_batch(ids["tenant_id"], device_id, [_update_operation(fuel_log_id, key, 91.0)])

    conflict = await _post_batch(ids["tenant_id"], device_id, [_update_operation(fuel_log_id, key, 99.0)])
    result = conflict.json()["results"][0]

    assert result["status"] == "conflict", f"a segunda correccao foi engolida: {result}"
    assert result["error_code"] == "idempotency_key_reused", result
    assert await _liters_of(ids["tenant_id"], fuel_log_id) == 91.0, "o conflito alterou o registo na mesma"


async def test_update_without_server_id_fails_alone() -> None:
    ids = await _seed()
    device_id = f"phone-{uuid4().hex[:8]}"
    stop_case = next(c for c in CASES if c.entity_type == "trip_stop")
    stops_before = await _count(TripStop, ids["tenant_id"])

    response = await _post_batch(
        ids["tenant_id"],
        device_id,
        [
            {
                "local_id": "local_update_no_id",
                "idempotency_key": str(uuid4()),
                "operation": "update",
                "entity_type": "fuel_log",
                "payload": {"liters": 91.0},
            },
            _operation(stop_case, ids, str(uuid4()), stop_case.payload(ids)),
        ],
    )

    assert response.status_code == 200, response.text
    results = {r["local_id"]: r for r in response.json()["results"]}
    assert results["local_update_no_id"]["status"] == "failed"
    assert results["local_update_no_id"]["error_code"] == "server_id_required"
    assert await _count(TripStop, ids["tenant_id"]) == stops_before + 1, (
        "a operacao valida foi descartada por causa do update sem server_id"
    )


async def test_update_with_a_malformed_server_id_does_not_abort_the_batch() -> None:
    """`UUID(server_id)` runs outside the update handler's own try block.

    Before failure isolation was added to the dispatcher, a corrupted id in the
    device queue — a truncated string, a local id that never got mapped — took
    the whole batch down with it.
    """
    ids = await _seed()
    device_id = f"phone-{uuid4().hex[:8]}"
    stop_case = next(c for c in CASES if c.entity_type == "trip_stop")
    stops_before = await _count(TripStop, ids["tenant_id"])

    response = await _post_batch(
        ids["tenant_id"],
        device_id,
        [
            {
                "local_id": "local_update_bad_uuid",
                "idempotency_key": str(uuid4()),
                "operation": "update",
                "entity_type": "fuel_log",
                "payload": {"serverId": "nao-e-um-uuid", "liters": 91.0},
            },
            _operation(stop_case, ids, str(uuid4()), stop_case.payload(ids)),
        ],
    )

    assert response.status_code == 200, f"um server_id corrompido derrubou o lote inteiro: {response.status_code}"
    results = {r["local_id"]: r for r in response.json()["results"]}
    assert results["local_update_bad_uuid"]["status"] == "failed"
    assert await _count(TripStop, ids["tenant_id"]) == stops_before + 1


async def test_update_cannot_reach_another_tenants_entity() -> None:
    """A device paired to tenant A must not patch tenant B's fuel log."""
    victim = await _seed()
    attacker = await _seed()
    victim_log_id = await _create_fuel_log(victim, f"phone-{uuid4().hex[:8]}")
    litres_before = await _liters_of(victim["tenant_id"], victim_log_id)

    response = await _post_batch(
        attacker["tenant_id"],
        f"phone-{uuid4().hex[:8]}",
        [_update_operation(victim_log_id, str(uuid4()), 999.0)],
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["status"] == "failed", response.text
    assert await _liters_of(victim["tenant_id"], victim_log_id) == litres_before, (
        "um tenant alterou o registo de combustivel de outro pelo lote de sincronizacao"
    )


async def test_trip_cost_syncs_without_the_client_inventing_a_second_key() -> None:
    """`request_reference` is derived from the operation's idempotency key.

    A trip cost is deduplicated by `request_reference`, unique per tenant. That
    is the same guarantee the sync key already carries, so requiring the device
    to generate and store a second identifier would be asking it to solve a
    problem it has already solved — and, until now, `trip_cost` was advertised
    in `bootstrap` as supported while every such operation failed validation.
    """
    ids = await _seed()
    tenant_id = ids["tenant_id"]
    device_id = f"phone-{uuid4().hex[:8]}"
    key = str(uuid4())
    payload = {
        "tripId": ids["trip_id"],
        "costType": "toll",
        "amount": 350.0,
        "currency": "MZN",
        "incurredAt": _now(),
        "description": "Portagem EN1",
    }
    operation = {
        "local_id": "local_cost_derived",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": "trip_cost",
        "payload": payload,
    }

    before = await _count(TripCost, tenant_id)

    first = await _post_batch(tenant_id, device_id, [operation])
    assert first.status_code == 200, first.text
    result = first.json()["results"][0]
    assert result["status"] == "processed", result
    assert await _count(TripCost, tenant_id) == before + 1

    # The derived reference must also make the retry safe at the domain level,
    # not only at the sync layer.
    replay = await _post_batch(tenant_id, device_id, [operation])
    assert replay.json()["results"][0]["server_id"] == result["server_id"]
    assert await _count(TripCost, tenant_id) == before + 1


async def test_an_explicit_request_reference_from_the_client_is_respected() -> None:
    """Deriving is a default, not an override: a device that sends its own wins."""
    ids = await _seed()
    device_id = f"phone-{uuid4().hex[:8]}"
    payload = {
        "tripId": ids["trip_id"],
        "costType": "fine",
        "amount": 1200.0,
        "currency": "MZN",
        "incurredAt": _now(),
        "requestReference": "multa-en1-2026-0042",
    }

    response = await _post_batch(
        ids["tenant_id"],
        device_id,
        [
            {
                "local_id": "local_cost_explicit",
                "idempotency_key": str(uuid4()),
                "operation": "create",
                "entity_type": "trip_cost",
                "payload": payload,
            }
        ],
    )
    assert response.json()["results"][0]["status"] == "processed", response.text

    async with AsyncSessionLocal() as db:
        stored = await db.scalar(
            select(TripCost.request_reference).where(
                TripCost.tenant_id == ids["tenant_id"]
            )
        )
    assert stored == "multa-en1-2026-0042", (
        f"a referencia enviada pelo dispositivo foi substituida por {stored!r}"
    )
