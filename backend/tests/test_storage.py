"""Tests for INFRA-02: storage.py dual-provider (LOCAL and R2)."""
import pytest

# Will import from app.storage once implemented
# from app.storage import upload_file, generate_presigned_url, StorageProvider


@pytest.mark.skip(reason="Wave 2 — storage.py not yet implemented")
async def test_local_upload_writes_to_disk(tmp_path):
    """LOCAL provider writes content bytes to disk at local_upload_dir/storage_key."""
    pass


@pytest.mark.skip(reason="Wave 2 — storage.py not yet implemented")
async def test_r2_upload_calls_put_object(monkeypatch):
    """R2 provider calls aiobotocore put_object with correct bucket and key.
    Uses monkeypatch to mock the aiobotocore session — no real R2 required."""
    pass


@pytest.mark.skip(reason="Wave 2 — storage.py not yet implemented")
async def test_local_presign_returns_sentinel():
    """LOCAL provider generate_presigned_url returns 'local://{storage_key}'."""
    pass


@pytest.mark.skip(reason="Wave 2 — storage.py not yet implemented")
async def test_r2_presign_calls_generate_presigned_url(monkeypatch):
    """R2 provider calls aiobotocore generate_presigned_url and returns real URL."""
    pass
