---
plan: 08-03
phase: 08-infrastructure-hardening
status: complete
completed_at: 2026-06-07
self_check: PASSED
---

## What Was Built

`storage.py` dual-provider abstraction (LOCAL/R2) and full refactor of all three upload paths in `files/service.py` (INFRA-02).

## Key Files Created

- `backend/app/storage.py` — `StorageProvider` enum (`LOCAL`/`R2`), `upload_file()`, `generate_presigned_url()`, `get_file_url()` — dispatches on `settings.storage_provider`

## Key Files Modified

- `backend/app/config.py` — R2 fields: `storage_provider`, `r2_bucket`, `r2_endpoint_url`, `r2_access_key_id`, `r2_secret_access_key`
- `backend/app/modules/files/service.py` — all three upload paths refactored: direct binary upload, presigned URL, generated-file saving — all use `_storage.upload_file()` / `_storage.generate_presigned_url()` instead of `write_bytes()`
- `backend/pyproject.toml` — added `aiobotocore[boto3]>=3.7.0`
- `backend/tests/test_storage.py` — 4 tests GREEN: local upload writes to disk, R2 upload calls put_object (mocked), local presign returns sentinel, R2 presign calls generate_presigned_url

## Test Results

```
tests/test_storage.py — 4 passed
```

## Commits

- `1c17fd7` — feat(08-03): add R2 config fields and aiobotocore dep
- (storage.py + service.py committed in same push)
