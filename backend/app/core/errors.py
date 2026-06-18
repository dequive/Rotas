from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.request_context import REQUEST_ID_HEADER, get_request_id, normalize_request_id


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def not_implemented(operation: str) -> ApiError:
    return ApiError(
        "not_implemented",
        f"Service implementation pending for {operation}.",
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        details={"operation": operation},
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    request_id = get_request_id() or normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
    return JSONResponse(
        status_code=exc.status_code,
        headers={REQUEST_ID_HEADER: request_id},
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
