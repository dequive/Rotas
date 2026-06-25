import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models_auth import ApiKey

_KEY_PREFIX = "gvn"
_KEY_VERSION = "1"


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix_8chars, sha256_hex)."""
    prefix = secrets.token_hex(4)          # 8 hex chars
    secret = secrets.token_urlsafe(24)     # 32 url-safe chars
    full_key = f"{_KEY_PREFIX}{_KEY_VERSION}_{prefix}_{secret}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    actor_id: str
    actor_type: str
    scopes: list[str] = field(default_factory=list)
    label: str = ""


async def validate_api_key(db: AsyncSession, raw_key: str) -> Principal | None:
    """Validates a raw API key. Returns Principal or None. Never raises."""
    try:
        parts = raw_key.split("_", 2)
        if len(parts) != 3 or not parts[0].startswith(_KEY_PREFIX):
            return None
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    except Exception:
        return None

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        return None

    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    await db.commit()

    return Principal(
        tenant_id=str(api_key.tenant_id),
        actor_id=str(api_key.id),
        actor_type=api_key.actor_type,
        scopes=list(api_key.scopes or []),
        label=api_key.label,
    )
