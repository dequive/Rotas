from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.files import schemas, service

router = APIRouter(prefix="/files", tags=["files"])
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_limited_upload(upload: UploadFile) -> bytes:
    mime_type = upload.content_type or "application/octet-stream"
    service.validate_upload_metadata(size_bytes=1, mime_type=mime_type)
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > service.MAX_UPLOAD_BYTES:
            raise ApiError(
                "invalid_file_size",
                "File size is outside the allowed range.",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                details={"max_upload_bytes": service.MAX_UPLOAD_BYTES},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/presign")
async def presign_upload(
    payload: schemas.PresignRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
        device_id=principal.device_id,
        idempotency_key=idempotency_key,
        operation="files.presign",
        entity_type="file",
        payload=payload,
        handler=lambda: service.presign_upload(
            db,
            principal.tenant_id,
            payload,
            user_id=principal.user_id,
            driver_id=principal.driver_id,
        ),
    )


@router.post("/upload")
async def upload_file(
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    upload: Annotated[UploadFile, File()],
    file_type: Annotated[str, Form()],
    entity_type: Annotated[str | None, Form()] = None,
    entity_id: Annotated[UUID | None, Form()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    content = await _read_limited_upload(upload)
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
        device_id=principal.device_id,
        idempotency_key=idempotency_key,
        operation="files.upload",
        entity_type="file",
        payload={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "file_type": file_type,
            "filename": upload.filename,
            "mime_type": upload.content_type,
            "sha256_hash": sha256(content).hexdigest(),
        },
        handler=lambda: service.upload_file(
            db,
            principal.tenant_id,
            principal,
            upload=upload,
            file_type=file_type,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
        ),
    )


@router.post("/confirm")
async def confirm_upload(
    payload: schemas.ConfirmUploadRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.confirm_upload(
        db,
        principal.tenant_id,
        payload,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
    )


@router.get("/{file_id}")
async def get_file(
    file_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_file(db, principal.tenant_id, file_id)


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    file, path = await service.get_file_path(db, principal.tenant_id, file_id)
    return FileResponse(
        path,
        media_type=file.mime_type,
        filename=file.original_name,
    )
