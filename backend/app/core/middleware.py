"""
INFRA2-02: HTTP request logging middleware.

Logs each request as a single structured JSON line AFTER the response is sent, with:
  - method, path, status_code, duration_ms
  - request_id (injected by RequestContextMiddleware via structlog contextvars)
  - Any additional context bound by the database session (tenant_id) is available
    if structlog contextvars are populated before the log call.

Placement: Add AFTER RequestContextMiddleware in main.py so request_id is in scope.
Starlette applies middlewares in reverse registration order — add this BEFORE
RequestContextMiddleware in app.add_middleware() calls.
"""
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("http")

# Paths to skip (health + metrics reduce noise in logs)
_SKIP_PATHS = frozenset(["/health", "/health/deep", "/metrics", "/favicon.ico"])


class StructlogRequestMiddleware(BaseHTTPMiddleware):
    """Emit one structured log line per HTTP request with timing information."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        path = request.url.path
        if path in _SKIP_PATHS:
            return response

        logger.info(
            "http_request",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
        )
        return response
