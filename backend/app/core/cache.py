import logging
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


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

