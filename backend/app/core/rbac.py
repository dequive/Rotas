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

# ── Role → Permission mapping ──────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": frozenset({
        # Owner holds every permission in the system
        FLEET_READ, FLEET_WRITE,
        DRIVERS_READ, DRIVERS_WRITE, DRIVERS_PAIRING,
        TRIPS_READ, TRIPS_DISPATCH, TRIPS_CLOSE,
        CARGO_WRITE, CARGO_VALIDATE,
        BILLING_READ, BILLING_WRITE, BILLING_ISSUE, BILLING_VOID,
        FUEL_READ, FUEL_WRITE, FUEL_APPROVE,
        WORKSHOP_READ, WORKSHOP_WRITE, WORKSHOP_RELEASE,
        ADMIN_USERS, ADMIN_TENANT,
        AUDIT_READ,
    }),
    "admin": frozenset({
        # Admin has all permissions except admin.tenant (tenant-level config reserved for owner)
        FLEET_READ, FLEET_WRITE,
        DRIVERS_READ, DRIVERS_WRITE, DRIVERS_PAIRING,
        TRIPS_READ, TRIPS_DISPATCH, TRIPS_CLOSE,
        CARGO_WRITE, CARGO_VALIDATE,
        BILLING_READ, BILLING_WRITE, BILLING_ISSUE, BILLING_VOID,
        FUEL_READ, FUEL_WRITE, FUEL_APPROVE,
        WORKSHOP_READ, WORKSHOP_WRITE, WORKSHOP_RELEASE,
        ADMIN_USERS,
        AUDIT_READ,
    }),
    "manager": frozenset({
        # Manager can operate fleet and financial workflows; cannot approve/void or manage users
        FLEET_READ, FLEET_WRITE,
        DRIVERS_READ, DRIVERS_WRITE,
        TRIPS_READ, TRIPS_DISPATCH, TRIPS_CLOSE,
        CARGO_WRITE, CARGO_VALIDATE,
        BILLING_READ, BILLING_WRITE, BILLING_ISSUE,
        FUEL_READ, FUEL_WRITE,
        WORKSHOP_READ, WORKSHOP_WRITE,
    }),
    "viewer": frozenset({
        # Viewer is read-only across core domains (no billing.read gap, no workshop write)
        FLEET_READ,
        DRIVERS_READ,
        TRIPS_READ,
        BILLING_READ,
        FUEL_READ,
        WORKSHOP_READ,
    }),
    "mechanic": frozenset({
        # Mechanic writes to workshop; read-only on fleet/drivers/trips/fuel; no billing access
        FLEET_READ,
        DRIVERS_READ,
        TRIPS_READ,
        FUEL_READ,
        WORKSHOP_READ,
        WORKSHOP_WRITE,
    }),
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
