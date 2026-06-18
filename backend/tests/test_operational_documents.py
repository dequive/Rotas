"""Phase 15.1 — Operational Documents integration tests.

Requirements: OPDOC-01, OPDOC-02, OPDOC-03, OPDOC-04, OPDOC-05
All tests require a live PostgreSQL DB.
"""
import pytest


# OPDOC-01 ────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="OPDOC-01: transport_documents DDL not yet applied")
async def test_transport_document_has_extra_fields_column(db, tenant_id):
    """TransportDocument ORM model must expose extra_fields, recipient_name,
    recipient_nuit after DDL migration."""
    ...

@pytest.mark.skip(reason="OPDOC-01: transport_documents DDL not yet applied")
async def test_extra_fields_accepts_jsonb_dict(db, tenant_id):
    """extra_fields column stores and retrieves arbitrary dict payloads
    (e.g., {border_post: 'Ressano Garcia', country_destination: 'ZA'})."""
    ...


# OPDOC-02 ────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="OPDOC-02: create_guia_remessa not yet implemented")
async def test_create_guia_remessa_returns_document_and_pdf_url(async_client, auth_headers):
    """POST /cargo/trips/{id}/guia-remessa returns 201 with document_id
    and a pdf_url pointing to the generated PDF."""
    ...

@pytest.mark.skip(reason="OPDOC-02: create_guia_remessa not yet implemented")
async def test_guia_remessa_requires_recipient_name(async_client, auth_headers):
    """POST /cargo/trips/{id}/guia-remessa returns 422 when recipient_name
    is missing from the payload."""
    ...

@pytest.mark.skip(reason="OPDOC-02: create_guia_remessa not yet implemented")
async def test_guia_remessa_cross_tenant_isolation(async_client, auth_headers):
    """Cannot create guia_remessa for a trip belonging to another tenant."""
    ...


# OPDOC-03 ────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="OPDOC-03: create_carta_porte not yet implemented")
async def test_create_carta_porte_stores_extra_fields(async_client, auth_headers):
    """POST /cargo/trips/{id}/carta-porte stores border_post and
    country_destination in extra_fields JSONB column."""
    ...

@pytest.mark.skip(reason="OPDOC-03: create_carta_porte not yet implemented")
async def test_carta_porte_pdf_accessible(async_client, auth_headers):
    """GET /cargo/transport-documents/{id}/pdf returns a PDF binary for
    a carta_porte_internacional document."""
    ...


# OPDOC-04 ────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="OPDOC-04: create_dav not yet implemented")
async def test_create_dav_stores_authorization_code(async_client, auth_headers):
    """POST /cargo/trips/{id}/dav stores authorization_code in extra_fields
    and document_number (INATTER-issued number) as top-level field."""
    ...

@pytest.mark.skip(reason="OPDOC-04: create_dav not yet implemented")
async def test_dav_has_no_pdf_generation(async_client, auth_headers):
    """DAV document does not generate a PDF (physical document issued by
    INATTER externally — digital record only)."""
    ...


# OPDOC-05 ────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="OPDOC-05: document-checklist not yet implemented")
async def test_checklist_domestic_trip_requires_four_doc_types(async_client, auth_headers):
    """GET /cargo/trips/{id}/document-checklist for a domestic (non-international,
    non-hazmat) trip returns exactly 4 required document types:
    cargo_manifest, load_permit, dav, guia_remessa."""
    ...

@pytest.mark.skip(reason="OPDOC-05: document-checklist not yet implemented")
async def test_checklist_international_trip_requires_five_doc_types(async_client, auth_headers):
    """GET /cargo/trips/{id}/document-checklist for an international trip
    returns at least 5 required types including carta_porte_internacional."""
    ...

@pytest.mark.skip(reason="OPDOC-05: document-checklist not yet implemented")
async def test_checklist_hazmat_adds_declaracao_carga_perigosa(async_client, auth_headers):
    """GET /cargo/trips/{id}/document-checklist for a hazmat trip includes
    declaracao_carga_perigosa in required list."""
    ...
