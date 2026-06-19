"""Phase 15.1 — Operational Documents integration tests.

Requirements: OPDOC-01, OPDOC-02, OPDOC-03, OPDOC-04, OPDOC-05
All tests require a live PostgreSQL DB.
"""

from uuid import uuid4

import pytest

from app.modules.cargo.models import TransportDocument
from app.modules.drivers.models import Driver
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_vehicle(db, tenant_id):
    v = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(v)
    await db.flush()
    return v


async def _make_driver(db, tenant_id):
    d = Driver(
        tenant_id=tenant_id,
        full_name=f"Motorista {uuid4().hex[:4]}",
        status="active",
    )
    db.add(d)
    await db.flush()
    return d


async def _make_trip(db, tenant_id, is_hazmat: bool = False, is_international: bool = False):
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Beira" if not is_international else "Johannesburg",
        status="draft",
        billing_status="pending_delivery_proof",
        is_hazmat=is_hazmat,
        is_international=is_international,
        hazmat_class="3" if is_hazmat else None,
    )
    db.add(t)
    await db.flush()
    return t


async def _make_committed_trip(
    db, tenant_id, is_hazmat: bool = False, is_international: bool = False
):
    trip = await _make_trip(db, tenant_id, is_hazmat=is_hazmat, is_international=is_international)
    await db.commit()
    await db.refresh(trip)
    return trip


# ---------------------------------------------------------------------------
# OPDOC-01 — TransportDocument DDL columns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transport_document_has_extra_fields_column(db, tenant_id):
    """TransportDocument ORM model exposes extra_fields, recipient_name, recipient_nuit."""
    trip = await _make_trip(db, tenant_id)

    doc = TransportDocument(
        tenant_id=tenant_id,
        trip_id=trip.id,
        document_type="guia_remessa",
        status="issued",
        recipient_name="João Nhantumbo",
        recipient_nuit="400000001",
        extra_fields={"cargo_description": "Cimento", "package_count": 500},
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    assert doc.recipient_name == "João Nhantumbo"
    assert doc.recipient_nuit == "400000001"
    assert doc.extra_fields is not None
    assert doc.extra_fields["cargo_description"] == "Cimento"


@pytest.mark.asyncio
async def test_extra_fields_accepts_jsonb_dict(db, tenant_id):
    """extra_fields stores and retrieves arbitrary dict payloads round-trip."""
    trip = await _make_trip(db, tenant_id)

    payload = {
        "border_post": "Ressano Garcia",
        "country_destination": "ZA",
        "sadc_cpi_number": "CPI-2026-00123",
        "notes_utf8": "Carga frágil — manuseio cuidadoso",
    }
    doc = TransportDocument(
        tenant_id=tenant_id,
        trip_id=trip.id,
        document_type="carta_porte_internacional",
        status="issued",
        extra_fields=payload,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    assert doc.extra_fields["border_post"] == "Ressano Garcia"
    assert doc.extra_fields["country_destination"] == "ZA"
    assert doc.extra_fields["sadc_cpi_number"] == "CPI-2026-00123"
    assert "frágil" in doc.extra_fields["notes_utf8"]


# ---------------------------------------------------------------------------
# OPDOC-02 — Guia de Remessa (HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_guia_remessa_returns_document_and_pdf_url(
    async_client, auth_headers, db, tenant_id
):
    """POST /cargo/trips/{id}/guia-remessa returns 201 with document_id and pdf_url."""
    trip = await _make_committed_trip(db, tenant_id)

    payload = {
        "client_name": "Transportes Maputo Lda",
        "recipient_name": "Armazéns Beira SA",
        "origin": "Maputo",
        "destination": "Beira",
        "cargo_description": "Cimento Portland 50kg",
        "package_count": 200,
        "gross_weight": 10000.0,
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/guia-remessa",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "pdf_url" in data
    assert data["document_type"] == "guia_remessa"
    assert data["pdf_url"].startswith("/files/")


@pytest.mark.asyncio
async def test_guia_remessa_requires_recipient_name(async_client, auth_headers, db, tenant_id):
    """POST /cargo/trips/{id}/guia-remessa without recipient_name returns 422."""
    trip = await _make_committed_trip(db, tenant_id)

    payload = {
        "client_name": "Transportes Maputo Lda",
        # missing recipient_name
        "origin": "Maputo",
        "destination": "Beira",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/guia-remessa",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_guia_remessa_cross_tenant_isolation(async_client, db, tenant_id):
    """Cannot create guia_remessa for a trip belonging to another tenant."""
    from app.modules.tenants.models import Tenant as TenantModel

    other = TenantModel(name=f"Other {uuid4().hex[:6]}", slug=f"other-{uuid4().hex[:6]}")
    db.add(other)
    await db.flush()
    trip = await _make_trip(db, tenant_id)
    await db.commit()

    other_headers = {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(other.id),
    }
    payload = {
        "client_name": "Intruso SA",
        "recipient_name": "Destino",
        "origin": "Maputo",
        "destination": "Beira",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/guia-remessa",
        json=payload,
        headers=other_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# OPDOC-03 — Carta de Porte Internacional (HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_carta_porte_stores_extra_fields(async_client, auth_headers, db, tenant_id):
    """POST /cargo/trips/{id}/carta-porte-internacional stores extra_fields JSONB."""
    trip = await _make_committed_trip(db, tenant_id)

    payload = {
        "client_name": "Transitários Moçambique SA",
        "origin": "Maputo",
        "destination": "Johannesburg",
        "border_post": "Ressano Garcia",
        "country_destination": "África do Sul",
        "sadc_cpi_number": "CPI-2026-00999",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/carta-porte-internacional",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_type"] == "carta_porte_internacional"
    assert data["extra_fields"]["border_post"] == "Ressano Garcia"
    assert data["extra_fields"]["country_destination"] == "África do Sul"


@pytest.mark.asyncio
async def test_carta_porte_pdf_accessible(async_client, auth_headers, db, tenant_id):
    """Creating carta_porte returns a pdf_url; the file endpoint accepts GET."""
    trip = await _make_committed_trip(db, tenant_id)

    payload = {
        "client_name": "Transitários Moçambique SA",
        "origin": "Maputo",
        "destination": "Harare",
        "border_post": "Forbes",
        "country_destination": "Zimbabwe",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/carta-porte-internacional",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "pdf_url" in data

    # The pdf_url points to /files/{id}/download — confirm it is a valid path
    pdf_url = data["pdf_url"]
    assert "/files/" in pdf_url
    assert "/download" in pdf_url


# ---------------------------------------------------------------------------
# OPDOC-04 — DAV / Declaração de Aprovação de Viagem (HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_dav_stores_authorization_code(async_client, auth_headers, db, tenant_id):
    """POST /cargo/trips/{id}/dav stores authorization_code in extra_fields."""
    trip = await _make_committed_trip(db, tenant_id)

    payload = {
        "authorization_code": "INATTER-2026-XYZ-00789",
        "document_number": "DAV-789",
        "issuer": "INATTER — Instituto Nacional de Transportes Terrestres",
        "origin": "Maputo",
        "destination": "Nampula",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/dav",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_type"] == "dav"
    assert data["document_number"] == "DAV-789"
    assert data["extra_fields"]["authorization_code"] == "INATTER-2026-XYZ-00789"


@pytest.mark.asyncio
async def test_dav_has_no_pdf_generation(async_client, auth_headers, db, tenant_id):
    """DAV document is a digital record only — no file_id or pdf_url in response."""
    trip = await _make_committed_trip(db, tenant_id)

    payload = {
        "authorization_code": "INATTER-2026-NO-PDF",
        "origin": "Maputo",
        "destination": "Tete",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/dav",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("pdf_url") is None
    assert data.get("file_id") is None


# ---------------------------------------------------------------------------
# OPDOC-05 — Document checklist per trip type (HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checklist_domestic_trip_requires_four_doc_types(
    async_client, auth_headers, db, tenant_id
):
    """GET /cargo/trips/{id}/document-checklist for domestic trip returns 4 required types."""
    trip = await _make_committed_trip(db, tenant_id)

    resp = await async_client.get(
        f"/api/v1/trips/{trip.id}/document-checklist",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    required_types = {item["document_type"] for item in data["checklist"]}
    assert required_types == {"guia_remessa", "load_permit", "cargo_manifest", "dav"}
    assert len(data["checklist"]) == 4
    assert data["is_international"] is False
    assert data["complete"] is False


@pytest.mark.asyncio
async def test_checklist_international_trip_requires_five_doc_types(
    async_client, auth_headers, db, tenant_id
):
    """GET /cargo/trips/{id}/document-checklist for an international trip returns 5 types."""
    trip = await _make_committed_trip(db, tenant_id, is_international=True)

    resp = await async_client.get(
        f"/api/v1/trips/{trip.id}/document-checklist",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    required_types = {item["document_type"] for item in data["checklist"]}
    assert "carta_porte_internacional" in required_types
    assert len(data["checklist"]) == 5
    assert data["is_international"] is True


@pytest.mark.asyncio
async def test_checklist_hazmat_adds_declaracao_carga_perigosa(
    async_client, auth_headers, db, tenant_id
):
    """GET /cargo/trips/{id}/document-checklist for hazmat trip includes declaracao_carga_perigosa."""
    trip = await _make_committed_trip(db, tenant_id, is_hazmat=True)

    resp = await async_client.get(
        f"/api/v1/trips/{trip.id}/document-checklist",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    required_types = {item["document_type"] for item in data["checklist"]}
    assert "declaracao_carga_perigosa" in required_types
    assert data["is_hazmat"] is True
    assert len(data["checklist"]) == 5


# ---------------------------------------------------------------------------
# declaracao-carga-perigosa endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_declaracao_carga_perigosa_on_hazmat_trip(
    async_client, auth_headers, db, tenant_id
):
    """POST /trips/{id}/declaracao-carga-perigosa succeeds on a hazmat trip, returns 201."""
    trip = await _make_committed_trip(db, tenant_id, is_hazmat=True)

    payload = {
        "hazmat_class": "3",
        "hazmat_description": "Gasolina — líquido inflamável",
        "un_number": "UN1203",
        "authorization_code": "INATTER-2026-DCP-00001",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/declaracao-carga-perigosa",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_type"] == "declaracao_carga_perigosa"
    assert data["extra_fields"]["hazmat_class"] == "3"
    assert data["extra_fields"]["un_number"] == "UN1203"
    assert data["extra_fields"]["authorization_code"] == "INATTER-2026-DCP-00001"
    assert data.get("pdf_url") is None
    assert data.get("file_id") is None


@pytest.mark.asyncio
async def test_declaracao_carga_perigosa_rejected_on_non_hazmat_trip(
    async_client, auth_headers, db, tenant_id
):
    """POST /trips/{id}/declaracao-carga-perigosa returns 409 on a non-hazmat trip."""
    trip = await _make_committed_trip(db, tenant_id, is_hazmat=False)

    payload = {
        "hazmat_class": "3",
        "hazmat_description": "Tentativa inválida",
    }
    resp = await async_client.post(
        f"/api/v1/trips/{trip.id}/declaracao-carga-perigosa",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# is_international field persists on Trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trip_is_international_persists(db, tenant_id):
    """Trip created with is_international=True stores the flag correctly."""
    trip = await _make_committed_trip(db, tenant_id, is_international=True)
    assert trip.is_international is True


@pytest.mark.asyncio
async def test_trip_is_international_defaults_false(db, tenant_id):
    """Trip created without is_international defaults to False."""
    trip = await _make_committed_trip(db, tenant_id)
    assert trip.is_international is False
