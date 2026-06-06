from contextlib import asynccontextmanager

import arq
import sentry_sdk
from arq.connections import RedisSettings as ArqRedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.errors import install_error_handlers
from app.core.limiter import limiter
from app.core.request_context import RequestContextMiddleware
from app.database import import_all_models
from app.modules.alerts.router import router as alerts_router
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import driver_router
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.cargo.router import router as cargo_router
from app.modules.checklists.router import router as checklists_router
from app.modules.contracts.router import router as contracts_router
from app.modules.control_tower.router import router as control_tower_router
from app.modules.drivers.router import router as drivers_router
from app.modules.files.router import router as files_router
from app.modules.fuel.operations_router import router as fuel_operations_router
from app.modules.fuel.router import router as fuel_router
from app.modules.operational_exceptions.router import router as operational_exceptions_router
from app.modules.operations.router import router as operations_router
from app.modules.sync.router import router as sync_router
from app.modules.tenants.router import router as tenants_router
from app.modules.trip_orders.router import router as trip_orders_router
from app.modules.trips.router import router as trips_router
from app.modules.trips.known_routes_router import router as known_routes_router
from app.modules.users.router import router as users_router
from app.modules.vehicles.router import router as vehicles_router
from app.modules.workshop.router import router as workshop_router

settings = get_settings()
import_all_models()

# INFRA-01: PII fields that must never appear in Sentry payloads (D-03)
_PII_FIELDS = frozenset([
    "driver_name", "cargo_description", "phone", "nuit", "email",
    "plate_number", "receiver_name", "receiver_contact",
])


def _scrub_dict(d: object) -> object:
    if not isinstance(d, dict):
        return d
    return {
        k: "[Filtered]" if k in _PII_FIELDS else _scrub_dict(v)
        for k, v in d.items()
    }


def _scrub_pii(event: dict, hint: dict) -> dict | None:
    """Strip PII from Sentry event before sending (INFRA-01 / D-03)."""
    # Scrub request.data (POST body)
    if "request" in event and "data" in event["request"]:
        event["request"]["data"] = _scrub_dict(event["request"]["data"])
    # Scrub extra context
    if "extra" in event:
        event["extra"] = _scrub_dict(event["extra"])
    # Scrub SQL breadcrumbs — remove 'data' key which may contain param values
    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        if breadcrumb.get("category") == "query":
            breadcrumb.pop("data", None)
    return event


@asynccontextmanager
async def lifespan(app: FastAPI):
    # INFRA-01: Sentry init — silent when DSN absent (D-02)
    if settings.sentry_dsn_backend:
        sentry_sdk.init(
            dsn=settings.sentry_dsn_backend,
            environment=settings.environment,
            traces_sample_rate=0.05,
            before_send=_scrub_pii,
        )

    # Initialize plain Redis client for CT cache-aside (redis.asyncio.Redis)
    try:
        app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await app.state.redis.ping()
    except Exception:
        # Redis unavailable — CT will fall back to direct DB queries
        app.state.redis = None

    # Initialize ARQ Redis pool for background job enqueue (arq.connections.ArqRedis)
    # NOTE: app.state.redis is for GET/SET cache ops; app.state.arq_redis is for enqueue_job()
    # They are DIFFERENT objects — do not substitute one for the other.
    try:
        app.state.arq_redis = await arq.create_pool(
            ArqRedisSettings.from_dsn(settings.redis_url)
        )
    except Exception:
        app.state.arq_redis = None

    yield

    if app.state.redis is not None:
        await app.state.redis.aclose()
    if app.state.arq_redis is not None:
        await app.state.arq_redis.aclose()


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
# SEC-03: Rate limiting — limiter state and 429 exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
install_error_handlers(app)
app.add_middleware(RequestContextMiddleware)

# SEC-02 / D-11: Always attach CORSMiddleware. In production, startup validator ensures
# cors_origins is non-empty. In development, empty list means no cross-origin requests allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["operation"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version", tags=["operation"])
async def version() -> dict[str, str]:
    return {"version": settings.version, "environment": settings.environment}


api = settings.api_v1_prefix
app.include_router(auth_router, prefix=api)
app.include_router(driver_router, prefix=api)
app.include_router(tenants_router, prefix=api)
app.include_router(contracts_router, prefix=api)
app.include_router(users_router, prefix=api)
app.include_router(vehicles_router, prefix=api)
app.include_router(drivers_router, prefix=api)
app.include_router(files_router, prefix=api)
app.include_router(checklists_router, prefix=api)
app.include_router(fuel_router, prefix=api)
app.include_router(fuel_operations_router, prefix=api)
app.include_router(trip_orders_router, prefix=api)
app.include_router(trips_router, prefix=api)
app.include_router(known_routes_router, prefix=api)
app.include_router(cargo_router, prefix=api)
app.include_router(billing_router, prefix=api)
app.include_router(operations_router, prefix=api)
app.include_router(operational_exceptions_router, prefix=api)
app.include_router(workshop_router, prefix=api)
app.include_router(control_tower_router, prefix=api)
app.include_router(alerts_router, prefix=api)
app.include_router(sync_router, prefix=api)
app.include_router(audit_router, prefix=api)
app.include_router(analytics_router, prefix=api)
