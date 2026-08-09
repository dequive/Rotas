from fastapi import Request
from slowapi import Limiter


def _api_key_or_ip(request: Request) -> str:
    key = request.headers.get("X-API-Key")
    if key:
        # Use the public prefix (first 20 chars) as the bucket identifier —
        # same key always hits the same bucket, but the full secret never enters logs.
        return f"key:{key[:20]}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


# Global default: 200 write operations per minute per API key (or IP as fallback).
# Sensitive endpoints override this with a tighter limit via @limiter.limit().
limiter = Limiter(key_func=_api_key_or_ip, default_limits=["200/minute"])
