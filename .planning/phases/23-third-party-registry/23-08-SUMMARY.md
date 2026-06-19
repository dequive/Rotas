---
phase: "23"
plan: "08"
subsystem: "third_party"
status: complete
tags: [party-directory, union-all, search, pagination]
dependency_graph:
  requires: ["02"]
  provides: [party_directory_endpoint, search_party_directory_service]
  affects: []
tech_stack:
  added: []
  patterns: [UNION ALL across 3 tables, subquery pagination, ILIKE name search]
key_files:
  created: []
  modified:
    - backend/app/modules/third_party/service.py
    - backend/app/modules/third_party/router.py
    - backend/tests/test_third_party.py
decisions:
  - "UNION ALL wraps each subquery in a named subquery ('party_union') then selects columns via sqlalchemy.column() — text() cannot be used for column list in select()"
  - "Client.is_active (boolean) cast to String to align with Driver.status and ThirdParty.status (VARCHAR)"
  - "Route /party-directory registered BEFORE /{tp_id} to prevent FastAPI matching 'party-directory' as a UUID tp_id"
  - "Single subject_type= query param (not multi-value list) per plan spec — converted to list internally"
metrics:
  duration: "15 minutes"
  completed_date: "2026-06-19"
  tasks_completed: 2
  files_changed: 3
---

# Phase 23 Plan 08: Party Directory UNION ALL Summary

## One-liner

`GET /api/v1/third-party/party-directory` returns a unified view of drivers, clients, and third parties via a single UNION ALL query, with optional `?subject_type=` filter, `?q=` name search (ILIKE), and limit/offset pagination.

## What Was Built

**service.py — `search_party_directory()`:**
- Builds sub-SELECTs for each entity type (driver, client, third_party), each scoped to `tenant_id`
- Optional ILIKE name search applied per-subquery before UNION
- Uses `union_all(*subqueries)` from SQLAlchemy, wrapped in `.subquery("party_union")`
- Outer SELECT uses `sqlalchemy.column()` for each column to correctly reference subquery columns
- ORDER BY `name ASC`, LIMIT/OFFSET applied on the outer query
- Client `is_active` (boolean) cast to `String` for type alignment across all three legs

**router.py — `GET /party-directory`:**
- `?q=` optional name search
- `?subject_type=` optional filter (single value → converted to `[subject_type]` list)
- Standard `limit`/`offset` pagination
- Registered before `/{tp_id}` to avoid path conflict
- `response_model=list[PartyDirectoryEntry]`

**Bug fix:** Initial implementation used `select(text("subject_id, subject_type, name, status"))` which SQLAlchemy treated as a single column expression — fixed to `select(column("subject_id"), column("subject_type"), column("name"), column("status"))`.

## Verification

Tests in `test_third_party.py`:
- `test_party_directory_union_all` — all 3 subject types returned, each row has required fields ✓
- `test_party_directory_filter_subject_type` — `?subject_type=third_party` returns ONLY third_party rows ✓
- `test_party_directory_name_search` — `?q=Américo` returns only matching driver ✓
- `test_party_directory_cross_tenant_isolation` — entries from tenant B absent from tenant A query ✓

## Self-Check: PASSED

- [x] UNION ALL query returns rows from all 3 entity types in one HTTP round trip
- [x] `?subject_type=third_party` returns ONLY third_party rows
- [x] `?q=` name search filters correctly (ILIKE)
- [x] Cross-tenant isolation verified
- [x] Route `/party-directory` does not conflict with `/{tp_id}` UUID route
