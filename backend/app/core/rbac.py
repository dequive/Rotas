"""Permission-based RBAC for ROTAS.

Naming convention: <domain>.<action>
  - Domain: module name (fleet, drivers, trips, cargo, billing, fuel, workshop, admin, audit)
  - Action: read | write | or a specific verb (dispatch, close, pairing, validate_delivery,
            issue, void_payment, approve_adjustment, release_vehicle, users, tenant)

Usage:
    from app.core.rbac import require_permission, TRIPS_DISPATCH

    @router.post("/trips/dispatch")
    async def dispatch_trip(
        principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
        ...
    ):

The existing require_roles() in permissions.py remains untouched as a compatibility shim.
Migrate call sites to require_permission() in subsequent plans (22-02 onward).
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, status

from app.core.errors import ApiError

# ── Permission string constants ────────────────────────────────────────────────

FLEET_READ = "fleet.read"
FLEET_WRITE = "fleet.write"

DRIVERS_READ = "drivers.read"
DRIVERS_WRITE = "drivers.write"
DRIVERS_PAIRING = "drivers.pairing"

TRIPS_READ = "trips.read"
TRIPS_DISPATCH = "trips.dispatch"
TRIPS_CLOSE = "trips.close"

CARGO_WRITE = "cargo.write"
CARGO_VALIDATE = "cargo.validate_delivery"

BILLING_READ = "billing.read"
BILLING_WRITE = "billing.write"
BILLING_ISSUE = "billing.issue"
BILLING_VOID = "billing.void_payment"

FUEL_READ = "fuel.read"
FUEL_WRITE = "fuel.write"
FUEL_APPROVE = "fuel.approve_adjustment"

WORKSHOP_READ = "workshop.read"
WORKSHOP_WRITE = "workshop.write"
WORKSHOP_RELEASE = "workshop.release_vehicle"

ADMIN_USERS = "admin.users"
ADMIN_TENANT = "admin.tenant"

AUDIT_READ = "audit.read"

# Stabilization/P0-F6: ERP module permissions (HR, Accounting, Payables, Inventory)
HR_READ = "hr.read"
HR_WRITE = "hr.write"
HR_SALARY_VIEW = "hr.salary.view"
HR_PAYROLL_GENERATE = "hr.payroll.generate"
HR_PAYROLL_APPROVE = "hr.payroll.approve"

ACCOUNTING_READ = "accounting.read"
ACCOUNTING_POST = "accounting.post"
ACCOUNTING_REVERSE = "accounting.reverse"

PAYABLES_READ = "payables.read"
PAYABLES_WRITE = "payables.write"
PAYABLES_APPROVE = "payables.approve"
PAYABLES_PAY = "payables.pay"

INVENTORY_READ = "inventory.read"
INVENTORY_WRITE = "inventory.write"
INVENTORY_ADJUST = "inventory.adjust"

# Role -> Permission mapping

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset(
        {
            # Owner holds every permission in the system
            FLEET_READ,
            FLEET_WRITE,
            DRIVERS_READ,
            DRIVERS_WRITE,
            DRIVERS_PAIRING,
            TRIPS_READ,
            TRIPS_DISPATCH,
            TRIPS_CLOSE,
            CARGO_WRITE,
            CARGO_VALIDATE,
            BILLING_READ,
            BILLING_WRITE,
            BILLING_ISSUE,
            BILLING_VOID,
            FUEL_READ,
            FUEL_WRITE,
            FUEL_APPROVE,
            WORKSHOP_READ,
            WORKSHOP_WRITE,
            WORKSHOP_RELEASE,
            ADMIN_USERS,
            ADMIN_TENANT,
            AUDIT_READ,
            # Stabilization/P0-F6: ERP modules
            HR_READ,
            HR_WRITE,
            HR_SALARY_VIEW,
            HR_PAYROLL_GENERATE,
            HR_PAYROLL_APPROVE,
            ACCOUNTING_READ,
            ACCOUNTING_POST,
            ACCOUNTING_REVERSE,
            PAYABLES_READ,
            PAYABLES_WRITE,
            PAYABLES_APPROVE,
            PAYABLES_PAY,
            INVENTORY_READ,
            INVENTORY_WRITE,
            INVENTORY_ADJUST,
        }
    ),
    "admin": frozenset(
        {
            # Admin has all permissions except admin.tenant (tenant-level config reserved for owner)
            FLEET_READ,
            FLEET_WRITE,
            DRIVERS_READ,
            DRIVERS_WRITE,
            DRIVERS_PAIRING,
            TRIPS_READ,
            TRIPS_DISPATCH,
            TRIPS_CLOSE,
            CARGO_WRITE,
            CARGO_VALIDATE,
            BILLING_READ,
            BILLING_WRITE,
            BILLING_ISSUE,
            BILLING_VOID,
            FUEL_READ,
            FUEL_WRITE,
            FUEL_APPROVE,
            WORKSHOP_READ,
            WORKSHOP_WRITE,
            WORKSHOP_RELEASE,
            ADMIN_USERS,
            AUDIT_READ,
            # Stabilization/P0-F6: ERP modules (admin can post but not reverse accounting)
            HR_READ,
            HR_WRITE,
            HR_SALARY_VIEW,
            HR_PAYROLL_GENERATE,
            ACCOUNTING_READ,
            ACCOUNTING_POST,
            PAYABLES_READ,
            PAYABLES_WRITE,
            PAYABLES_APPROVE,
            PAYABLES_PAY,
            INVENTORY_READ,
            INVENTORY_WRITE,
            INVENTORY_ADJUST,
        }
    ),
    "manager": frozenset(
        {
            # Manager can operate fleet and financial workflows; cannot approve/void or manage users
            FLEET_READ,
            FLEET_WRITE,
            DRIVERS_READ,
            DRIVERS_WRITE,
            TRIPS_READ,
            TRIPS_DISPATCH,
            TRIPS_CLOSE,
            CARGO_WRITE,
            CARGO_VALIDATE,
            BILLING_READ,
            BILLING_WRITE,
            BILLING_ISSUE,
            FUEL_READ,
            FUEL_WRITE,
            WORKSHOP_READ,
            WORKSHOP_WRITE,
            # Stabilization/P0-F6: billing approval, payroll approve, accounting approve
            HR_READ,
            HR_WRITE,
            HR_PAYROLL_GENERATE,
            ACCOUNTING_READ,
            ACCOUNTING_POST,
            PAYABLES_READ,
            PAYABLES_WRITE,
            PAYABLES_PAY,
            INVENTORY_READ,
            INVENTORY_WRITE,
        }
    ),
    "viewer": frozenset(
        {
            # Viewer is read-only across core domains (no billing.read gap, no workshop write)
            FLEET_READ,
            DRIVERS_READ,
            TRIPS_READ,
            BILLING_READ,
            FUEL_READ,
            WORKSHOP_READ,
            # Stabilization/P0-F6: read-only ERP, no salary visibility
            HR_READ,
            ACCOUNTING_READ,
            PAYABLES_READ,
            INVENTORY_READ,
        }
    ),
    "mechanic": frozenset(
        {
            # Mechanic writes to workshop; read-only on fleet/drivers/trips/fuel; no billing access
            FLEET_READ,
            DRIVERS_READ,
            TRIPS_READ,
            FUEL_READ,
            WORKSHOP_READ,
            WORKSHOP_WRITE,
        }
    ),
}

# ── ALL_PERMISSIONS: union of every role's permission set ─────────────────────
# Should equal exactly 23 unique permission strings.
ALL_PERMISSIONS: frozenset[str] = frozenset().union(*ROLE_PERMISSIONS.values())


# ── require_permission() FastAPI dependency factory ───────────────────────────


def require_permission(*permissions: str) -> Callable:
    """FastAPI dependency factory.

    Returns an async dependency that checks the current principal holds AT LEAST
    ONE of the listed permissions. On success, returns the principal unchanged so
    callers can bind it: `Depends(require_permission(TRIPS_DISPATCH))`.

    On failure: raises ApiError 403 with sorted list of required permissions so the
    client knows what was expected (frozenset serialized to list — avoids JSON errors).

    Circular import note: this function imports Principal via TYPE_CHECKING only.
    The actual runtime import happens inside get_current_principal() which is imported
    here without touching auth.py's Principal class at module load time.
    """
    # Import at call time to avoid circular import at module level.
    # Principal must be a concrete type (not a string forward-ref) so FastAPI's
    # get_type_hints() can resolve it and recognise the Depends() annotation rather
    # than treating `principal` as a query parameter.
    from app.core.auth import Principal, get_current_principal  # noqa: PLC0415

    required: frozenset[str] = frozenset(permissions)

    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if not principal.has_any_permission(required):
            raise ApiError(
                "forbidden",
                "Insufficient permissions for this operation.",
                status_code=status.HTTP_403_FORBIDDEN,
                details={"required_permissions": sorted(required)},
            )
        return principal

    return dependency


# ── Platform role constants (Phase 25) ────────────────────────────────────────

PLATFORM_ADMIN = "platform_admin"
PLATFORM_SUPPORT = "platform_support"
PLATFORM_BILLING = "platform_billing"

PLATFORM_ROLES: frozenset[str] = frozenset({PLATFORM_ADMIN, PLATFORM_SUPPORT, PLATFORM_BILLING})


def require_platform_role(*roles: str) -> Callable:
    """FastAPI dependency for platform-scoped endpoints.

    Validation is dual and ordered:
      1. Delegates to get_current_platform_principal() which ONLY accepts scope="platform" tokens.
         A tenant JWT (scope="dashboard") is rejected at the decode step with 403 — role is never
         read. This prevents a tenant user with a custom role named "platform_admin" from gaining
         access (scope check fires BEFORE role check).
      2. Checks that principal.role is in the allowed set.
    """
    from app.core.auth import Principal, get_current_platform_principal  # noqa: PLC0415

    allowed: frozenset[str] = frozenset(roles)

    async def dependency(
        principal: Annotated[Principal, Depends(get_current_platform_principal)],
    ) -> Principal:
        # Scope already validated by get_current_platform_principal.
        # Belt-and-suspenders: assert it here so this guard is self-contained.
        if principal.scope != "platform":
            raise ApiError(
                "forbidden",
                "Platform scope required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if principal.role not in allowed:
            raise ApiError(
                "forbidden",
                "Insufficient platform role for this operation.",
                status_code=status.HTTP_403_FORBIDDEN,
                details={"required_roles": sorted(allowed)},
            )
        return principal

    return dependency


# ── require_own_tenant_or_platform() — combined guard (Phase 25 Plan 03) ──────


def require_own_tenant_or_platform(
    tenant_permission: str = ADMIN_USERS,
) -> Callable:
    """Combined guard for endpoints accessible to BOTH tenant admins and platform_admin.

    Resolves the principal from whichever scope the token belongs to:
      - scope="dashboard": delegates to get_current_principal and checks
        tenant_permission. Returns tenant Principal with tenant_id set.
      - scope="platform": calls get_current_platform_principal and requires
        role=PLATFORM_ADMIN. Other platform roles (support, billing) are rejected
        with 403 — they use the dedicated /platform/* read endpoints instead.
        Returns platform Principal with tenant_id=None.
      - Any other scope: 401 from the underlying decoder.

    The returned principal MUST be inspected by the route handler:
      - If principal.scope == "platform": use a ?tenant_id= query param for
        tenant context (passed in by the caller; this guard does not inject it).
      - If principal.scope == "dashboard": use principal.tenant_id (own tenant only).
    """
    import base64  # noqa: PLC0415
    import json  # noqa: PLC0415

    from fastapi import Request  # noqa: PLC0415

    from app.core.auth import (  # noqa: PLC0415
        Principal,
        get_current_platform_principal,
        get_current_principal,
    )

    async def dependency(request: Request) -> Principal:
        # Read headers directly from the Request object.
        # FastAPI always injects Request correctly regardless of closure scope —
        # unlike Header() annotations which fail to resolve in factory-returned closures.
        authorization: str | None = request.headers.get("Authorization")
        x_tenant_id_raw: str | None = request.headers.get("X-Tenant-Id")
        x_tenant_id: UUID | None = UUID(x_tenant_id_raw) if x_tenant_id_raw else None

        if not authorization or not authorization.lower().startswith("bearer "):
            raise ApiError(
                "unauthorized",
                "Authentication token is required.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        # Peek at the JWT scope claim to choose the correct decoder.
        # Full cryptographic validation happens inside the delegated function — no bypass here.
        token = authorization.split(" ", 1)[1]
        try:
            payload_b64 = token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            raw_claims = json.loads(base64.urlsafe_b64decode(payload_b64))
            token_scope = raw_claims.get("scope", "")
        except Exception:
            token_scope = ""

        if token_scope == "platform":
            # Full decode + DB lookup via the platform-specific decoder.
            principal = await get_current_platform_principal(authorization=authorization)
            # Only platform_admin may use tenant-plane endpoints directly.
            if principal.role != PLATFORM_ADMIN:
                raise ApiError(
                    "forbidden",
                    "Only platform_admin can access tenant configuration endpoints directly."
                    " platform_support and platform_billing should use /platform/tenants/{id}.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            return principal
        else:
            # Tenant path: full validation via the tenant decoder.
            principal = await get_current_principal(
                authorization=authorization, x_tenant_id=x_tenant_id
            )
            if not principal.has_any_permission(frozenset({tenant_permission})):
                raise ApiError(
                    "forbidden",
                    "Insufficient permissions for this operation.",
                    status_code=status.HTTP_403_FORBIDDEN,
                    details={"required_permissions": [tenant_permission]},
                )
            return principal

    return dependency
