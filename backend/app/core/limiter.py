"""
INFRA2-01: Redis-backed rate limiter for multi-worker Railway deployment.

Previously used in-memory Limiter (D-07 from Phase 4 — deferred to this phase).
Redis instance is the same as ARQ worker and Control Tower cache.

Rate limits enforced per-endpoint in routers:
  - /auth/login: 10/minute per IP  (SEC-03)
  - /driver-auth/pair: 10/minute per IP  (SEC-03)
  - /api/v1/sync/batch: 60/minute per IP
  - /api/v1/gps/webhook/*: 60/minute per IP  (Phase 12)
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()

# INFRA2-01: Use Redis storage so rate limit counters are shared across all
# Gunicorn workers. Falls back gracefully to in-memory if REDIS_URL is absent
# (local dev without Redis). In production, REDIS_URL must always be set.
if _settings.redis_url:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=_settings.redis_url,
    )
else:
    import warnings

    warnings.warn(
        "REDIS_URL not set — rate limiter using in-memory storage. "
        "Multi-worker deployments will have independent rate limit counters.",
        RuntimeWarning,
        stacklevel=1,
    )
    limiter = Limiter(key_func=get_remote_address)
