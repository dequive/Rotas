from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.files import schemas, service

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/presign")
async def presign_upload(
    payload: schemas.PresignRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    upload: Annotated[UploadFile, File()],
    file_type: Annotated[str, Form()],
    entity_type: Annotated[str | None, Form()] = None,
    entity_id: Annotated[UUID | None, Form()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    content = await upload.read()
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
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_file(db, principal.tenant_id, file_id)


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    file, path = await service.get_file_path(db, principal.tenant_id, file_id)
    return FileResponse(
        path,
        media_type=file.mime_type,
        filename=file.original_name,
    )
