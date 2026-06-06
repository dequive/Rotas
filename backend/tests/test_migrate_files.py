"""Tests for INFRA-02: R2 migration script behavior."""
import pytest


@pytest.mark.skip(reason="Wave 2 — migrate_files_to_r2.py not yet implemented")
async def test_migration_skips_missing_file(tmp_path):
    """Script skips a File record whose local path does not exist on disk.
    Continues to next record without raising. Failure appears in summary."""
    pass


@pytest.mark.skip(reason="Wave 2 — migrate_files_to_r2.py not yet implemented")
async def test_migration_exits_1_on_failures():
    """Script exits with code 1 when any file failed to migrate."""
    pass


@pytest.mark.skip(reason="Wave 2 — migrate_files_to_r2.py not yet implemented")
async def test_migration_exits_0_on_clean():
    """Script exits with code 0 when all files migrated successfully."""
    pass


@pytest.mark.skip(reason="Wave 2 — migrate_files_to_r2.py not yet implemented")
async def test_gate_query_zero_local_records(db):
    """After successful migration, SELECT count(*) FROM files WHERE
    storage_provider IN ('local', 'local_stub') returns 0."""
    pass
