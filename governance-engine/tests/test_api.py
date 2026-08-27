"""HTTP API tests — auth, occurrences, cases, error codes."""

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient


async def test_unauthenticated_request_returns_401(taxonomy):
    from httpx import ASGITransport, AsyncClient

    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/occurrences/")
    assert r.status_code == 401


async def test_health_no_auth():
    from httpx import ASGITransport, AsyncClient

    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_create_occurrence(client: AsyncClient, taxonomy):
    idem_key = str(uuid.uuid4())
    r = await client.post(
        "/api/v1/occurrences/",
        json={
            "type_code": taxonomy["occ_type"].code,
            "severity": "baixa",
            "title": "Test via HTTP",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
        headers={"Idempotency-Key": idem_key},
    )
    assert r.status_code == 201
    data = r.json()
    assert "occurrence_id" in data
    assert data["numero"].startswith("EVT-")


async def test_create_occurrence_idempotent(client: AsyncClient, taxonomy):
    idem_key = str(uuid.uuid4())
    payload = {
        "type_code": taxonomy["occ_type"].code,
        "severity": "baixa",
        "title": "Idempotent test",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    r1 = await client.post(
        "/api/v1/occurrences/", json=payload, headers={"Idempotency-Key": idem_key}
    )
    r2 = await client.post(
        "/api/v1/occurrences/", json=payload, headers={"Idempotency-Key": idem_key}
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["occurrence_id"] == r2.json()["occurrence_id"]


async def test_create_occurrence_auto_promotes(client: AsyncClient, taxonomy):
    r = await client.post(
        "/api/v1/occurrences/",
        json={
            "type_code": taxonomy["occ_type"].code,
            "severity": "alta",
            "title": "High severity",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["case_id"] is not None
    assert data["case_reference"].startswith("CASE-")


async def test_get_occurrence(client: AsyncClient, taxonomy):
    idem_key = str(uuid.uuid4())
    r_create = await client.post(
        "/api/v1/occurrences/",
        json={
            "type_code": taxonomy["occ_type"].code,
            "severity": "baixa",
            "title": "Get test",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
        headers={"Idempotency-Key": idem_key},
    )
    occ_id = r_create.json()["occurrence_id"]
    r_get = await client.get(f"/api/v1/occurrences/{occ_id}")
    assert r_get.status_code == 200
    assert r_get.json()["id"] == occ_id


async def test_create_case(client: AsyncClient, taxonomy):
    r = await client.post(
        "/api/v1/cases/",
        json={"case_type_code": taxonomy["case_type"].code, "payload": {}},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "open"
    assert data["reference"].startswith("CASE-")


async def test_apply_valid_transition(client: AsyncClient, taxonomy):
    r_case = await client.post(
        "/api/v1/cases/",
        json={"case_type_code": taxonomy["case_type"].code},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    case_id = r_case.json()["id"]

    r_trans = await client.post(
        f"/api/v1/cases/{case_id}/transitions",
        json={"to_status": "in_analysis"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_trans.status_code == 201
    assert r_trans.json()["to_status"] == "in_analysis"


async def test_illegal_transition_returns_409(client: AsyncClient, taxonomy):
    r_case = await client.post(
        "/api/v1/cases/",
        json={"case_type_code": taxonomy["case_type"].code},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    case_id = r_case.json()["id"]

    r_trans = await client.post(
        f"/api/v1/cases/{case_id}/transitions",
        json={"to_status": "closed"},  # no rule open → closed
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_trans.status_code == 409
    assert r_trans.json()["code"] == "illegal_transition"


async def test_missing_required_field_returns_422(client: AsyncClient, taxonomy):
    r_case = await client.post(
        "/api/v1/cases/",
        json={"case_type_code": taxonomy["case_type"].code},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    case_id = r_case.json()["id"]

    # open → resolved requires resolution_note
    r_trans = await client.post(
        f"/api/v1/cases/{case_id}/transitions",
        json={"to_status": "resolved", "payload": {}},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_trans.status_code == 422
    assert r_trans.json()["code"] == "missing_required_field"
    assert r_trans.json()["field"] == "resolution_note"


async def test_available_transitions(client: AsyncClient, taxonomy):
    r_case = await client.post(
        "/api/v1/cases/",
        json={"case_type_code": taxonomy["case_type"].code},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    case_id = r_case.json()["id"]
    r_avail = await client.get(f"/api/v1/cases/{case_id}/transitions/available")
    assert r_avail.status_code == 200
    to_statuses = {t["to_status"] for t in r_avail.json()}
    assert "in_analysis" in to_statuses


async def test_list_cases(client: AsyncClient, taxonomy):
    # Create two cases
    for _ in range(2):
        await client.post(
            "/api/v1/cases/",
            json={"case_type_code": taxonomy["case_type"].code},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
    r = await client.get("/api/v1/cases/")
    assert r.status_code == 200
    assert r.json()["total"] >= 2
    assert len(r.json()["items"]) >= 2


async def test_list_active_case_types(client: AsyncClient, taxonomy):
    r = await client.get("/api/v1/cases/types/")

    assert r.status_code == 200
    assert {
        "id": str(taxonomy["case_type"].id),
        "code": taxonomy["case_type"].code,
        "name": taxonomy["case_type"].name,
        "initial_status": taxonomy["case_type"].initial_status,
        "sla_hours": taxonomy["case_type"].sla_hours,
    } in r.json()


async def test_reverse_occurrence(client: AsyncClient, taxonomy):
    r_create = await client.post(
        "/api/v1/occurrences/",
        json={
            "type_code": taxonomy["occ_type"].code,
            "severity": "baixa",
            "title": "To reverse",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    occ_id = r_create.json()["occurrence_id"]

    r_rev = await client.post(
        f"/api/v1/occurrences/{occ_id}/reverse",
        json={"reason": "Entered in error during testing"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert r_rev.status_code == 201
    assert r_rev.json()["occurrence_id"] != occ_id
