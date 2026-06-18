---
plan: 08-04
phase: 08-infrastructure-hardening
status: complete
completed_at: 2026-06-07
self_check: PASSED
---

## What Was Built

ARQ worker billing export routed through files module (no more direct disk writes), ExportJob.file_id FK added, one-shot R2 migration script (INFRA-02).

## Key Files Created

- `backend/alembic/versions/f0a1b2c3d4e5_add_export_job_file_id.py` — adds `file_id` nullable FK to `files.id` on `export_jobs` table; revises `e1f2a3b4c5d6`
- `backend/scripts/migrate_files_to_r2.py` — one-shot migration: queries `storage_provider IN ('local','local_stub')`, uploads to R2 via aiobotocore, updates `storage_provider='r2'`, skip-on-missing-file, exits 0/1

## Key Files Modified

- `backend/app/modules/billing/models.py` — added `file_id: Mapped[uuid.UUID | None]` FK after `file_path`
- `backend/app/worker.py` — `generate_billing_export()` now calls `save_generated_file()` from files/service.py; sets `job.file_id = file_obj.id`; `job.file_path = file_obj.storage_key` kept for backward compat
- `backend/tests/test_migrate_files.py` — 4 tests implemented (skip-on-missing, exit-1-on-error, exit-0-clean, gate-query-zero)

## Test Results

```
tests/test_migrate_files.py — 4 passed
alembic upgrade head — clean (f0a1b2c3d4e5 applied)
```

## Commits

- `623893d` — feat(08-04): add ExportJob.file_id FK to files table + Alembic migration
- `b1f9b40` — feat(08-04): route worker billing export through files module + R2 migration script
