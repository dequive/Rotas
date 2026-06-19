"""Tests for INFRA-02: storage.py dual-provider (LOCAL and R2)."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.storage import StorageProvider, generate_presigned_url, upload_file


async def test_local_upload_writes_to_disk(tmp_path, monkeypatch):
    """LOCAL provider writes content bytes to disk at local_upload_dir/storage_key."""
    from app import storage as storage_mod

    tenant_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    storage_key = f"{tenant_id}/documents/file123_test.pdf"
    content = b"PDF content here"

    # Point local_upload_dir to tmp_path
    settings_mock = MagicMock()
    settings_mock.storage_provider = "local"
    settings_mock.local_upload_dir = str(tmp_path)
    monkeypatch.setattr(storage_mod, "get_settings", lambda: settings_mock)

    result = await upload_file(storage_key, content, mime_type="application/pdf")

    assert result == StorageProvider.LOCAL
    # storage_key relative part is after first "/"
    relative = storage_key.split("/", maxsplit=1)[1]
    written = tmp_path / relative
    assert written.exists()
    assert written.read_bytes() == content


async def test_local_upload_rejects_path_traversal(tmp_path, monkeypatch):
    from app import storage as storage_mod

    settings_mock = MagicMock()
    settings_mock.storage_provider = "local"
    settings_mock.local_upload_dir = str(tmp_path)
    monkeypatch.setattr(storage_mod, "get_settings", lambda: settings_mock)

    try:
        await upload_file("tenant-id/../escape.pdf", b"bad", mime_type="application/pdf")
    except ValueError as exc:
        assert "outside local_upload_dir" in str(exc)
    else:
        raise AssertionError("Expected path traversal storage_key to be rejected")


async def test_r2_upload_calls_put_object(monkeypatch):
    """R2 provider calls aiobotocore put_object with correct bucket and key.
    Uses monkeypatch to mock the aiobotocore session — no real R2 required."""
    from app import storage as storage_mod

    tenant_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    storage_key = f"{tenant_id}/documents/file123_test.pdf"
    content = b"PDF content here"

    settings_mock = MagicMock()
    settings_mock.storage_provider = "r2"
    settings_mock.r2_bucket = "rotas-bucket"
    settings_mock.r2_endpoint_url = "https://account.r2.cloudflarestorage.com"
    settings_mock.r2_access_key_id = "key_id"
    settings_mock.r2_secret_access_key.get_secret_value.return_value = "secret"
    monkeypatch.setattr(storage_mod, "get_settings", lambda: settings_mock)

    mock_client = AsyncMock()
    mock_client.put_object = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.create_client.return_value = mock_client

    with patch("aiobotocore.session.get_session", return_value=mock_session):
        result = await upload_file(storage_key, content, mime_type="application/pdf")

    assert result == StorageProvider.R2
    mock_client.put_object.assert_called_once_with(
        Bucket="rotas-bucket",
        Key=storage_key,
        Body=content,
        ContentType="application/pdf",
    )


async def test_local_presign_returns_sentinel(monkeypatch):
    """LOCAL provider generate_presigned_url returns 'local://{storage_key}'."""
    from app import storage as storage_mod

    storage_key = "tenant-id/documents/file123_test.pdf"

    settings_mock = MagicMock()
    settings_mock.storage_provider = "local"
    monkeypatch.setattr(storage_mod, "get_settings", lambda: settings_mock)

    result = await generate_presigned_url(storage_key)

    assert result == f"local://{storage_key}"


async def test_r2_presign_calls_generate_presigned_url(monkeypatch):
    """R2 provider calls aiobotocore generate_presigned_url and returns real URL."""
    from app import storage as storage_mod

    storage_key = "tenant-id/documents/file123_test.pdf"
    expected_url = "https://account.r2.cloudflarestorage.com/rotas-bucket/tenant-id/documents/file123_test.pdf?X-Amz-Signature=abc123"

    settings_mock = MagicMock()
    settings_mock.storage_provider = "r2"
    settings_mock.r2_bucket = "rotas-bucket"
    settings_mock.r2_endpoint_url = "https://account.r2.cloudflarestorage.com"
    settings_mock.r2_access_key_id = "key_id"
    settings_mock.r2_secret_access_key.get_secret_value.return_value = "secret"
    monkeypatch.setattr(storage_mod, "get_settings", lambda: settings_mock)

    mock_client = AsyncMock()
    mock_client.generate_presigned_url = AsyncMock(return_value=expected_url)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.create_client.return_value = mock_client

    with patch("aiobotocore.session.get_session", return_value=mock_session):
        result = await generate_presigned_url(storage_key, expires_in=900)

    assert result == expected_url
    mock_client.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={"Bucket": "rotas-bucket", "Key": storage_key},
        ExpiresIn=900,
    )
