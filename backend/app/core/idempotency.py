import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.sync.models import IdempotencyKey

IDEMPOTENCY_TTL_DAYS = 30
IDEMPOTENCY_BILLING_TTL_DAYS = 90


def canonical_request_hash(payload: Any) -> str:
    canonical = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ttl_for(entity_type: str) -> int:
    if entity_type in {"billing_document", "billing_item"}:
        return IDEMPOTENCY_BILLING_TTL_DAYS
    return IDEMPOTENCY_TTL_DAYS


async def execute_http_idempotent(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    idempotency_key: str | None,
    operation: str,
    entity_type: str,
    payload: Any,
    handler: Callable[[], Awaitable[dict]],
    user_id: UUID | None = None,
    driver_id: UUID | None = None,
    device_id: str | None = None,
) -> dict:
    if not idempotency_key:
        return await handler()
    request_hash = canonical_request_hash(
        {"operation": operation, "entity_type": entity_type, "payload": payload}
    )
    reserved = IdempotencyKey(
        tenant_id=tenant_id,
        driver_id=driver_id,
        device_id=device_id or (f"user:{user_id}" if user_id else None),
        idempotency_key=idempotency_key,
        operation=operation,
        entity_type=entity_type,
        request_hash=request_hash,
        expires_at=datetime.now(UTC) + timedelta(days=ttl_for(entity_type)),
    )
    db.add(reserved)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        existing = await db.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.idempotency_key == idempotency_key,
            )
        )
        if not existing or existing.request_hash != request_hash:
            raise ApiError(
                "idempotency_key_reused",
                "Idempotency key was reused with a different request.",
                status_code=409,
            ) from exc
        if existing.response_body is None:
            raise ApiError(
                "idempotency_request_in_progress",
                "A request with this idempotency key is already in progress.",
                status_code=423,
            ) from exc
        return existing.response_body

    try:
        response = await handler()
    except ApiError:
        await db.delete(reserved)
        await db.commit()
        raise
    reserved.response_body = jsonable_encoder(response)
    reserved.status_code = 200
    entity_id = response.get("id")
    if entity_id:
        reserved.entity_id = UUID(str(entity_id))
    await db.commit()
    return response
