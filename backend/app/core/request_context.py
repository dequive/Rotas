from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.core.performance_diagnostics import (
    begin_request_timings,
    render_server_timing,
    reset_request_timings,
)

REQUEST_ID_HEADER = "x-request-id"
MAX_REQUEST_ID_LENGTH = 128

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def normalize_request_id(value: str | None) -> str:
    request_id = value.strip() if value else ""
    if not request_id or len(request_id) > MAX_REQUEST_ID_LENGTH:
        return uuid4().hex
    return request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.performance_diagnostics = get_settings().performance_diagnostics

    async def dispatch(self, request: Request, call_next):
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = _request_id.set(request_id)
        timing_token = (
            begin_request_timings() if self.performance_diagnostics else None
        )
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            if timing_token is not None:
                server_timing = render_server_timing()
                if server_timing:
                    response.headers["Server-Timing"] = server_timing
            return response
        finally:
            if timing_token is not None:
                reset_request_timings(timing_token)
            _request_id.reset(token)
