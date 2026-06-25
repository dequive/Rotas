from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from adapters.rotas.router import router as rotas_router
from api.admin import router as admin_router
from api.cases import router as cases_router
from api.occurrences import router as occurrences_router
from api.platform import router as platform_router
from core.config import get_settings
from core.database import AsyncSessionLocal
from core.exceptions import GovernanceError, MissingRequiredField
from core.limiter import limiter
from core.logging_config import configure_logging
from core.middleware import RequestIdMiddleware

settings = get_settings()
configure_logging(level=settings.log_level)

app = FastAPI(
    title="Governance Engine",
    description="Sistema Nervoso Central para Governança e Memória Institucional",
    version="1.0.0",
)

# Attach rate limiter state before any middleware/handlers are registered
app.state.limiter = limiter

# Middleware — Starlette builds a stack where each add_middleware wraps around all
# previously added middleware. The net execution order (outermost first) is:
#   RequestIdMiddleware → SlowAPIMiddleware → CORSMiddleware → App
app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)   # 429s are tagged with Request-Id by outer layer
app.add_middleware(RequestIdMiddleware)


# ── Exception handlers ────────────────────────────────────────────────────────

_CODE_TO_STATUS: dict[str, int] = {
    "not_found":                   404,
    "illegal_transition":          409,
    "idempotency_conflict":        409,
    "missing_required_field":      422,
    "missing_required_attachment": 422,
    "tenant_isolation_violation":  403,
}


@app.exception_handler(GovernanceError)
async def governance_error_handler(_request: Request, exc: GovernanceError) -> JSONResponse:
    status = _CODE_TO_STATUS.get(exc.code, 400)
    body: dict = {"code": exc.code, "message": exc.message}
    if isinstance(exc, MissingRequiredField):
        body["field"] = exc.field
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"code": "rate_limit_exceeded", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Normalise Pydantic validation errors to the same envelope as domain errors.
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(loc) for loc in first.get("loc", [])[1:]) or "unknown"
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": first.get("msg", "Validation error."),
            "field": field,
            "errors": [
                {"field": ".".join(str(l) for l in e.get("loc", [])[1:]), "message": e.get("msg", "")}
                for e in errors
            ],
        },
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(_request: Request, exc: PermissionError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"code": "forbidden", "message": str(exc)})


# ── Routers ───────────────────────────────────────────────────────────────────

PREFIX = "/api/v1"

app.include_router(occurrences_router, prefix=PREFIX)
app.include_router(cases_router,       prefix=PREFIX)
app.include_router(admin_router,       prefix=PREFIX)
app.include_router(rotas_router,       prefix=PREFIX)
app.include_router(platform_router,    prefix=PREFIX)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health() -> dict:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"

    status_code = 200 if db_status == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if db_status == "ok" else "degraded", "db": db_status, "version": "1.0.0"},
    )
