"""Dual-provider file storage abstraction (LOCAL and R2/S3).

Dispatch logic: reads settings.storage_provider at call time.
Usage: from app.storage import upload_file, generate_presigned_url, StorageProvider
"""
from enum import Enum
from pathlib import Path

import aiobotocore.session

from app.config import get_settings


class StorageProvider(str, Enum):
    LOCAL = "local"
    R2 = "r2"


def _local_path(storage_key: str) -> Path:
    """Return absolute disk path for a storage_key under local_upload_dir."""
    settings = get_settings()
    root = Path(settings.local_upload_dir)
    # storage_key format: "{tenant_id}/{entity_type}/{file_id}_{filename}"
    # Strip leading tenant segment when building path (matches _tenant_upload_dir pattern)
    relative = storage_key.split("/", maxsplit=1)[1] if "/" in storage_key else storage_key
    return root / relative


async def upload_file(storage_key: str, content: bytes, *, mime_type: str) -> StorageProvider:
    """Upload bytes to configured storage provider. Returns provider used."""
    settings = get_settings()
    if settings.storage_provider.lower() == StorageProvider.R2:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        ) as client:
            await client.put_object(
                Bucket=settings.r2_bucket,
                Key=storage_key,
                Body=content,
                ContentType=mime_type,
            )
        return StorageProvider.R2
    else:
        target = _local_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StorageProvider.LOCAL


async def generate_presigned_url(storage_key: str, *, expires_in: int = 900) -> str:
    """Return a presigned PUT URL (R2) or local sentinel (LOCAL)."""
    settings = get_settings()
    if settings.storage_provider.lower() == StorageProvider.R2:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        ) as client:
            url = await client.generate_presigned_url(
                "put_object",
                Params={"Bucket": settings.r2_bucket, "Key": storage_key},
                ExpiresIn=expires_in,
            )
        return url
    else:
        return f"local://{storage_key}"


async def get_file_url(storage_key: str, *, expires_in: int = 3600) -> str | None:
    """Return a presigned GET URL for a file. Returns None if LOCAL (no public URL)."""
    settings = get_settings()
    if settings.storage_provider.lower() == StorageProvider.R2:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
        ) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.r2_bucket, "Key": storage_key},
                ExpiresIn=expires_in,
            )
    return None
