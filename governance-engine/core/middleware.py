"""
Request ID + structured access logging middleware.

Sets X-Request-Id on every response. Logs method, path, status, and
duration_ms as a single JSON line per request via the structured logger.
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logging_config import request_id_var

logger = logging.getLogger("governance.access")

_MAX_REQUEST_ID_LEN = 128


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        raw = request.headers.get("X-Request-Id", "")
        req_id = raw[:_MAX_REQUEST_ID_LEN] if raw else uuid.uuid4().hex

        token = request_id_var.set(req_id)
        t0 = time.monotonic()
        response: Response | None = None
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.monotonic() - t0) * 1000)
            status_code = response.status_code if response is not None else 500
            logger.info(
                "%s %s %d",
                request.method,
                request.url.path,
                status_code,
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)

        assert response is not None
        response.headers["X-Request-Id"] = req_id
        return response
