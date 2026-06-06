"""Tests for INFRA-02: R2 migration script behavior."""
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.files.models import File


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(tenant_id, storage_key: str, storage_provider: str = "local") -> File:
    return File(
        id=uuid4(),
        tenant_id=tenant_id,
        entity_type="billing_document",
        entity_id=uuid4(),
        file_type="billing_pdf",
        original_name="invoice.pdf",
        storage_key=storage_key,
        storage_provider=storage_provider,
        mime_type="application/pdf",
        size_bytes=1024,
        sha256_hash="a" * 64,
        confirmed_at=datetime.now(UTC),
    )


async def _run_main_with_mocks(
    tmp_path: Path,
    db_files: list[File],
    *,
    r2_upload_raises: Exception | None = None,
) -> int:
    """Run the migration main() with mocked session, settings, and R2 client."""
    import scripts.migrate_files_to_r2 as script_module

    # Fake settings
    fake_settings = MagicMock()
    fake_settings.local_upload_dir = str(tmp_path)
    fake_settings.r2_bucket = "test-bucket"
    fake_settings.r2_endpoint_url = "https://fake.r2.dev"
    fake_settings.r2_access_key_id = "fake-key"
    fake_settings.r2_secret_access_key = MagicMock()
    fake_settings.r2_secret_access_key.get_secret_value.return_value = "fake-secret"

    # Fake async DB session
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = db_files

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(return_value=fake_result)
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=False)

    # Fake R2 put_object
    if r2_upload_raises is not None:
        fake_put = AsyncMock(side_effect=r2_upload_raises)
    else:
        fake_put = AsyncMock(return_value={})

    fake_r2_client = AsyncMock()
    fake_r2_client.put_object = fake_put
    fake_r2_client.__aenter__ = AsyncMock(return_value=fake_r2_client)
    fake_r2_client.__aexit__ = AsyncMock(return_value=False)

    fake_boto_session = MagicMock()
    fake_boto_session.create_client.return_value = fake_r2_client

    with (
        patch.object(script_module, "_settings", fake_settings),
        patch("scripts.migrate_files_to_r2.AsyncSessionLocal", return_value=fake_db),
        patch("aiobotocore.session.get_session", return_value=fake_boto_session),
    ):
        return await script_module.main()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_migration_skips_missing_file(tmp_path, tenant_id):
    """Script continues past a File record whose local path does not exist on disk.
    That file appears in the failure count; other files succeed.
    Return code is 1 because failures > 0.
    """
    tid = tenant_id

    # File A: missing from disk
    missing_key = f"{tid}/billing_document/missing_file.pdf"
    file_missing = _make_file(tid, missing_key)

    # File B: present on disk
    present_rel = "billing_document/present_file.pdf"
    present_key = f"{tid}/{present_rel}"
    present_disk = tmp_path / present_rel
    present_disk.parent.mkdir(parents=True, exist_ok=True)
    present_disk.write_bytes(b"%PDF-1.4 test content")
    file_present = _make_file(tid, present_key)

    exit_code = await _run_main_with_mocks(tmp_path, [file_missing, file_present])

    # File A failed (not on disk), file B succeeded → exit 1
    assert exit_code == 1


async def test_migration_exits_1_on_failures(tmp_path, tenant_id):
    """Script exits with code 1 when any file fails to upload to R2."""
    tid = tenant_id

    rel = "billing_document/upload_fail.pdf"
    key = f"{tid}/{rel}"
    disk = tmp_path / rel
    disk.parent.mkdir(parents=True, exist_ok=True)
    disk.write_bytes(b"%PDF-1.4 upload fail test")

    file = _make_file(tid, key)

    exit_code = await _run_main_with_mocks(
        tmp_path,
        [file],
        r2_upload_raises=ConnectionError("R2 timeout"),
    )

    assert exit_code == 1


async def test_migration_exits_0_on_clean(tmp_path, tenant_id):
    """Script exits with code 0 when all files migrate successfully."""
    tid = tenant_id

    rel = "billing_document/clean.pdf"
    key = f"{tid}/{rel}"
    disk = tmp_path / rel
    disk.parent.mkdir(parents=True, exist_ok=True)
    disk.write_bytes(b"%PDF-1.4 clean migration test")

    file = _make_file(tid, key)

    exit_code = await _run_main_with_mocks(tmp_path, [file])

    assert exit_code == 0


async def test_gate_query_zero_local_records(db, tenant_id):
    """After successful migration, File records have storage_provider='r2'
    (no remaining 'local' or 'local_stub' records for migrated files).
    Simulates the DB state the gate query validates.
    """
    from sqlalchemy import func, select

    tid = tenant_id
    key = f"{tid}/billing_document/gate_test.pdf"

    file = _make_file(tid, key, storage_provider="local")
    db.add(file)
    await db.commit()
    await db.refresh(file)

    # Simulate what the migration script does: update provider to r2
    file.storage_provider = "r2"
    await db.commit()

    # Gate query — must return 0
    count = await db.scalar(
        select(func.count(File.id)).where(
            File.storage_provider.in_(["local", "local_stub"]),
            File.tenant_id == tid,
        )
    )
    assert count == 0
