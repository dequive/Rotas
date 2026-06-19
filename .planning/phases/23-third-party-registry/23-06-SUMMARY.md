---
phase: 23-third-party-registry
plan: "06"
subsystem: third-party
tags: [operational-documents, partyref, polymorphic, rls, documents]
dependency_graph:
  requires: [23-01, 23-05]
  provides: [operational_documents table, document CRUD endpoints, expiry query]
  affects: [third_party module, files module (read), audit module]
tech_stack:
  added: []
  patterns:
    - PartyRef polymorphic pattern (subject_type + subject_id, no DB-level FK)
    - File tenant isolation validated at service layer via db.get(File, file_id)
    - Partial index on expiry_date WHERE expiry_date IS NOT NULL
key_files:
  created:
    - backend/alembic/versions/tp06_add_operational_documents.py
  modified:
    - backend/app/modules/third_party/models.py
    - backend/app/modules/third_party/schemas.py
    - backend/app/modules/third_party/service.py
    - backend/app/modules/third_party/router.py
decisions:
  - GET /documents/expiring registered before GET /documents/{doc_id} to prevent path shadowing
  - subject_type validation enforced at service layer (not DB CHECK constraint) to allow future extension
  - file_id cross-tenant check uses db.get(File, id) — minimal query, no join overhead
  - verify endpoint uses POST (not PATCH) to match plan spec; status constrained via Pydantic regex
metrics:
  duration: ~20 minutes
  completed: "2026-06-19"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 5
---

# Phase 23 Plan 06: Operational Documents Summary

**One-liner:** Polymorphic `operational_documents` table with PartyRef pattern, file-tenant isolation, verification workflow, and expiry window query using RLS.

## What Was Built

### Task 1 — Alembic migration `tp06_add_operational_documents.py`

- `CREATE TABLE operational_documents` with all columns per spec
- `down_revision = "tp01b"` (depends on Plan 01 only)
- Indexes: `ix_operational_documents_tenant_subject` (composite), `ix_operational_documents_expiry_date` (partial, WHERE expiry_date IS NOT NULL), `ix_operational_documents_tenant`, `ix_operational_documents_verification`
- RLS: `tenant_isolation` policy + `GRANT SELECT, INSERT, UPDATE, DELETE ON operational_documents TO rotas_app`
- Commit: `29c4637`

### Task 2 — ORM model, schemas, service, router

**models.py** — `OperationalDocument` class appended with full column set including `subject_type`, `subject_id` (polymorphic, no DB FK), `file_id` (nullable FK to `files.id` with `ON DELETE SET NULL`), `verification_status` (default `pending`), `verified_by`, `verified_at`.

**schemas.py** — Added `VALID_SUBJECT_TYPES`, `DocumentCreate`, `DocumentVerify` (regex-constrained to `verified|rejected`), `DocumentOut`.

**service.py** — Added:
- `serialize_document(doc)` serializer
- `create_document(db, tenant_id, payload, actor_id)` — validates `subject_type` membership, validates `file_id` tenant ownership via `db.get(File, id)`, audits `operational_document.created`
- `list_documents(db, tenant_id, *, subject_type, subject_id, verification_status, limit, offset)` — all params optional
- `verify_document(db, tenant_id, doc_id, payload, actor_id)` — sets `verification_status`, `verified_by`, `verified_at`, audits `operational_document.verified`
- `get_expiring_documents(db, tenant_id, days_ahead)` — window query `expiry_date >= today AND expiry_date <= today + timedelta(days=days_ahead)`

**router.py** — Added four endpoints registered before `/{tp_id}` catch-all:
- `POST /api/v1/third-party/documents` → 201
- `GET /api/v1/third-party/documents/expiring?days_ahead=30` (registered before `/documents/{doc_id}/verify` to prevent shadow)
- `GET /api/v1/third-party/documents?subject_type=&subject_id=&verification_status=&limit=&offset=`
- `POST /api/v1/third-party/documents/{doc_id}/verify`

Commit: `4d7f52c`

## Deviations from Plan

None — plan executed exactly as written. The `service.py` and `router.py` files were pre-created by Plan 05 executor; content was appended without overwriting.

## Acceptance Criteria Verification

| Criterion | Status |
|---|---|
| Migration `tp06_add_operational_documents.py` with RLS + GRANT | Done — `29c4637` |
| `OperationalDocument` ORM model in `models.py` | Done |
| `POST /api/v1/third-party/documents` with `subject_type` validation | Done — `create_document` validates against `VALID_SUBJECT_TYPES` |
| `get_expiring_documents(db, tenant_id, days_ahead)` returns window | Done — `expiry_date >= today AND <= today + days_ahead` |
| Cross-tenant: tenant B query returns empty for tenant A docs | Enforced by RLS `tenant_isolation` policy + `WHERE tenant_id == tenant_id` service filter |
| `file_id` from different tenant returns 404 | Done — `db.get(File, file_id)` + `file.tenant_id != tenant_id` check |

## Known Stubs

None — all endpoints are wired to real service functions with DB queries.

## Self-Check: PASSED

- `backend/alembic/versions/tp06_add_operational_documents.py` — FOUND
- `OperationalDocument` in `models.py` — FOUND (line 224+)
- `serialize_document` + `create_document` + `get_expiring_documents` in `service.py` — FOUND (lines 536, 557, 659)
- Document endpoints in `router.py` — FOUND (lines 72-120)
- Commits `29c4637` and `4d7f52c` — verified in git log
