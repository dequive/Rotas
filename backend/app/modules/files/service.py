from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage as _storage
from app.config import get_settings
from app.core.auth import Principal
from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.files.models import File
from app.modules.files.schemas import ConfirmUploadRequest, PresignRequest

LOCAL_UPLOAD_PROVIDER = "local"  # Deprecated — use StorageProvider.LOCAL from app.storage
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def serialize_file(file: File) -> dict:
    return {
        "id": file.id,
        "tenant_id": file.tenant_id,
        "entity_type": file.entity_type,
        "entity_id": file.entity_id,
        "file_type": file.file_type,
        "original_name": file.original_name,
        "storage_key": file.storage_key,
        "storage_provider": file.storage_provider,
        "mime_type": file.mime_type,
        "size_bytes": file.size_bytes,
        "sha256_hash": file.sha256_hash,
        "uploaded_by_user_id": file.uploaded_by_user_id,
        "uploaded_by_driver_id": file.uploaded_by_driver_id,
        "uploaded_at": file.uploaded_at,
        "confirmed_at": file.confirmed_at,
    }


def _safe_filename(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {".", "-", "_"} else "_" for char in value)
    return safe[:120] or "upload.bin"


def _tenant_upload_dir(tenant_id: UUID) -> Path:
    root = Path(get_settings().local_upload_dir)
    return root / str(tenant_id)


async def _require_file(db: AsyncSession, tenant_id: UUID, file_id: UUID) -> File:
    file = await db.get(File, file_id)
    if not file or file.tenant_id != tenant_id:
        raise ApiError("file_not_found", "File not found.", status_code=status.HTTP_404_NOT_FOUND)
    return file


async def presign_upload(
    db: AsyncSession,
    tenant_id: UUID,
    payload: PresignRequest,
    *,
    user_id: UUID | None = None,
    driver_id: UUID | None = None,
) -> dict:
    validate_upload_metadata(
        size_bytes=payload.size_bytes,
        mime_type=payload.mime_type,
        sha256_hash=payload.sha256_hash,
    )

    file_id = uuid4()
    storage_key = (
        f"{tenant_id}/{payload.entity_type}/{file_id}_{_safe_filename(payload.original_name)}"
    )
    upload_url = await _storage.generate_presigned_url(storage_key)
    file = File(
        id=file_id,
        tenant_id=tenant_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        file_type=payload.file_type,
        original_name=payload.original_name,
        storage_key=storage_key,
        storage_provider=get_settings().storage_provider,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        sha256_hash=payload.sha256_hash.lower(),
    )
    db.add(file)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        driver_id=driver_id,
        action="file.presigned",
        entity_type="file",
        entity_id=file.id,
        new_values=serialize_file(file),
    )
    await db.commit()

    return {
        "file_id": file_id,
        "upload_url": upload_url,
        "storage_key": storage_key,
        "expires_in": int(timedelta(minutes=15).total_seconds()),
    }


def validate_upload_metadata(
    *,
    size_bytes: int,
    mime_type: str,
    sha256_hash: str | None = None,
) -> None:
    if size_bytes <= 0 or size_bytes > MAX_UPLOAD_BYTES:
        raise ApiError(
            "invalid_file_size",
            "File size is outside the allowed range.",
            status_code=(
                status.HTTP_413_CONTENT_TOO_LARGE
                if size_bytes > MAX_UPLOAD_BYTES
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            details={"max_upload_bytes": MAX_UPLOAD_BYTES},
        )
    if mime_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise ApiError(
            "unsupported_mime_type",
            "File MIME type is not supported.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            details={"allowed_mime_types": sorted(ALLOWED_UPLOAD_MIME_TYPES)},
        )
    if sha256_hash is not None and (
        len(sha256_hash) != 64 or any(char not in "0123456789abcdefABCDEF" for char in sha256_hash)
    ):
        raise ApiError(
            "invalid_sha256_hash",
            "File SHA-256 hash must contain 64 hexadecimal characters.",
            status_code=422,
        )


async def upload_file(
    db: AsyncSession,
    tenant_id: UUID,
    principal: Principal,
    *,
    upload: UploadFile,
    file_type: str,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    content: bytes | None = None,
) -> dict:
    content = content if content is not None else await upload.read()
    if not content:
        raise ApiError(
            "empty_file",
            "Uploaded file cannot be empty.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    mime_type = upload.content_type or "application/octet-stream"
    validate_upload_metadata(size_bytes=len(content), mime_type=mime_type)

    file_id = uuid4()
    original_name = upload.filename or "upload.bin"
    storage_key = (
        f"{tenant_id}/{entity_type or 'unlinked'}/{file_id}_{_safe_filename(original_name)}"
    )
    provider = await _storage.upload_file(storage_key, content, mime_type=mime_type)

    file = File(
        id=file_id,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_type=file_type,
        original_name=original_name,
        storage_key=storage_key,
        storage_provider=provider.value,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256_hash=sha256(content).hexdigest(),
        uploaded_by_user_id=principal.user_id,
        uploaded_by_driver_id=principal.driver_id,
        confirmed_at=datetime.now(UTC),
    )
    db.add(file)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
        action="file.uploaded",
        entity_type="file",
        entity_id=file.id,
        new_values=serialize_file(file),
    )
    await db.commit()
    await db.refresh(file)
    return serialize_file(file)


async def save_generated_file(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    content: bytes,
    filename: str,
    mime_type: str,
    file_type: str,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> File:
    if not content:
        raise ApiError(
            "empty_generated_file",
            "Generated file cannot be empty.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    file_id = uuid4()
    storage_key = f"{tenant_id}/{entity_type or 'generated'}/{file_id}_{_safe_filename(filename)}"
    provider = await _storage.upload_file(storage_key, content, mime_type=mime_type)

    file = File(
        id=file_id,
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_type=file_type,
        original_name=filename,
        storage_key=storage_key,
        storage_provider=provider.value,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256_hash=sha256(content).hexdigest(),
        confirmed_at=datetime.now(UTC),
    )
    db.add(file)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        action="file.generated",
        entity_type="file",
        entity_id=file.id,
        new_values=serialize_file(file),
    )
    return file


async def confirm_upload(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ConfirmUploadRequest,
    *,
    user_id: UUID | None = None,
    driver_id: UUID | None = None,
) -> dict:
    file = await _require_file(db, tenant_id, payload.file_id)
    if (
        file.confirmed_at is not None
        and (payload.entity_type is None or payload.entity_type == file.entity_type)
        and (payload.entity_id is None or payload.entity_id == file.entity_id)
    ):
        return serialize_file(file)
    old_values = serialize_file(file)
    if payload.entity_type is not None:
        file.entity_type = payload.entity_type
    if payload.entity_id is not None:
        file.entity_id = payload.entity_id
    file.confirmed_at = datetime.now(UTC)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        driver_id=driver_id,
        action="file.confirmed",
        entity_type="file",
        entity_id=file.id,
        old_values=old_values,
        new_values=serialize_file(file),
    )
    await db.commit()
    await db.refresh(file)
    return serialize_file(file)


async def get_file(db: AsyncSession, tenant_id: UUID, file_id: UUID) -> dict:
    file = await _require_file(db, tenant_id, file_id)
    return serialize_file(file)


async def get_file_path(db: AsyncSession, tenant_id: UUID, file_id: UUID) -> tuple[File, Path]:
    file = await _require_file(db, tenant_id, file_id)
    # LOCAL only — R2 files must use presigned URL endpoint instead
    if file.storage_provider not in ("local", "local_stub"):
        raise ApiError(
            "file_not_local",
            "File is stored in R2. Use the presigned URL endpoint to download.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if "/" not in file.storage_key:
        raise ApiError(
            "invalid_storage_key",
            "Stored file path is invalid.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    key_tenant, relative_key = file.storage_key.split("/", maxsplit=1)
    if key_tenant != str(tenant_id):
        raise ApiError(
            "invalid_storage_key",
            "Stored file path does not match tenant context.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    root = Path(get_settings().local_upload_dir).resolve()
    path = (root / relative_key).resolve()
    if not path.is_relative_to(root):
        raise ApiError(
            "invalid_storage_key",
            "Stored file path is outside the upload directory.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if not path.exists():
        raise ApiError(
            "file_content_not_found",
            "File content is not available in storage.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return file, path


async def get_file_download_target(
    db: AsyncSession,
    tenant_id: UUID,
    file_id: UUID,
) -> tuple[File, Path | str]:
    file = await _require_file(db, tenant_id, file_id)
    if file.storage_provider in ("local", "local_stub"):
        return await get_file_path(db, tenant_id, file_id)
    if "/" not in file.storage_key or file.storage_key.split("/", maxsplit=1)[0] != str(
        tenant_id
    ):
        raise ApiError(
            "invalid_storage_key",
            "Stored file path does not match tenant context.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    url = await _storage.get_file_url(file.storage_key)
    if not url:
        raise ApiError(
            "file_storage_unavailable",
            "File storage is temporarily unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return file, url
