import logging
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class AsyncRedisHashClient(Protocol):
    """Minimal decoded-response Redis contract used by plan-limit counters."""

    async def hget(self, name: str, key: str) -> str | None: ...

    async def hset(self, name: str, key: str, value: str) -> int: ...

    async def expire(self, name: str, time: int) -> bool: ...


async def invalidate_keys(redis: Redis | None, pattern: str) -> None:
    """Invalidate all keys matching the pattern in Redis."""
    if redis is None:
        return
    try:
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
            logger.info(f"Invalidated {len(keys)} keys matching pattern: {pattern}")
    except Exception as e:
        logger.error(f"Failed to invalidate keys for pattern {pattern}: {e}")


async def invalidate_tenant_caches(redis: Redis | None, tenant_id: UUID) -> None:
    """Invalidate all cached read endpoints for the given tenant."""
    if redis is None:
        return
    pattern = f"tenant:{tenant_id}:*"
    await invalidate_keys(redis, pattern)
    # Also invalidate the limits cache key
    try:
        await redis.delete(f"tenant:limits:{tenant_id}")
    except Exception as e:
        logger.error(f"Failed to delete limits cache key for tenant {tenant_id}: {e}")
