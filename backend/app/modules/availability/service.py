from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.drivers.models import Driver
from app.modules.operations.models import OperationalWaiver
from app.modules.operations.service import has_active_waiver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder

ACTIVE_TRIP_STATUSES = (
    "planned",
    "dispatch_pending",
    "dispatched",
    "in_progress",
    "delayed",
    "incident",
)
ACTIVE_WORK_ORDER_STATUSES = ("approved", "in_progress", "quality_check")
DEFAULT_COMPLIANCE_WARNING_DAYS = 30


def _today() -> date:
    return datetime.now(UTC).date()


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _document_valid_until(documents: dict, document_type: str) -> date | None:
    nested = documents.get(document_type)
    if isinstance(nested, dict):
        nested_value = nested.get("valid_until") or nested.get("expires_at")
        parsed = _parse_date(nested_value)
        if parsed:
            return parsed
    flat_value = (
        documents.get(f"{document_type}_valid_until")
        or documents.get(f"{document_type}_expires_at")
        or documents.get(f"{document_type}_expiry")
    )
    return _parse_date(flat_value)


def _tenant_policy(tenant: Tenant | None) -> dict:
    return tenant.compliance_policy if tenant and tenant.compliance_policy else {}


def _required_documents(policy: dict, key: str) -> list[str]:
    values = policy.get(key)
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if value]


def _warning_days(policy: dict) -> int:
    value = policy.get("document_expiry_warning_days", DEFAULT_COMPLIANCE_WARNING_DAYS)
    if not isinstance(value, int) or value < 0:
        return DEFAULT_COMPLIANCE_WARNING_DAYS
    return value


def _is_expiring_soon(valid_until: date, *, policy: dict) -> bool:
    today = _today()
    return today <= valid_until <= today + timedelta(days=_warning_days(policy))


def vehicle_compliance_violations(
    vehicle: Vehicle,
    *,
    policy: dict | None = None,
) -> list[dict]:
    policy = policy or {}
    documents = vehicle.documents or {}
    required_documents = list(_required_documents(policy, "vehicle_required_documents"))
    vehicle_required_documents = documents.get("required_documents")
    if isinstance(vehicle_required_documents, list):
        required_documents.extend(str(item) for item in vehicle_required_documents if item)
    if not required_documents and documents.get("compliance_required"):
        required_documents = ["insurance", "inspection", "iav", "sign_tax", "cargo_book", "international_license"]
    if not required_documents:
        return []

    today = _today()
    violations = []
    for document_type in dict.fromkeys(required_documents):
        valid_until = _document_valid_until(documents, str(document_type))
        if valid_until is None:
            violations.append(
                {
                    "code": "missing_document",
                    "document_type": str(document_type),
                }
            )
            continue
        if valid_until < today:
            violations.append(
                {
                    "code": "expired_document",
                    "document_type": str(document_type),
                    "valid_until": valid_until.isoformat(),
                }
            )
    return violations


def vehicle_compliance_warnings(
    vehicle: Vehicle,
    *,
    policy: dict | None = None,
) -> list[dict]:
    policy = policy or {}
    documents = vehicle.documents or {}
    required_documents = list(_required_documents(policy, "vehicle_required_documents"))
    vehicle_required_documents = documents.get("required_documents")
    if isinstance(vehicle_required_documents, list):
        required_documents.extend(str(item) for item in vehicle_required_documents if item)
    if not required_documents and documents.get("compliance_required"):
        required_documents = ["insurance", "inspection", "iav", "sign_tax", "cargo_book", "international_license"]

    warnings = []
    for document_type in dict.fromkeys(required_documents):
        valid_until = _document_valid_until(documents, str(document_type))
        if valid_until and _is_expiring_soon(valid_until, policy=policy):
            warnings.append(
                {
                    "code": "document_expiring",
                    "document_type": str(document_type),
                    "valid_until": valid_until.isoformat(),
                    "days_until_expiry": (valid_until - _today()).days,
                }
            )
    return warnings


def driver_compliance_violations(
    driver: Driver,
    *,
    policy: dict | None = None,
) -> list[dict]:
    """Return compliance violations for a driver.

    Two violation types with different scoping rules:

    - expired_document: raised for any of {driving_license, passport, bi} where
      valid_until is set AND is in the past. No policy required — an expired date
      is always a violation regardless of tenant configuration.

    - missing_document: raised only when the tenant policy explicitly lists the
      document type in driver_required_documents AND valid_until is None. Matches
      vehicle_compliance_violations() behavior — "missing" is a policy choice, not
      a universal default, so operators can onboard drivers without all dates upfront.
    """
    policy = policy or {}
    today = _today()
    violations = []
    required_for_missing = set(_required_documents(policy, "driver_required_documents"))

    candidates = {
        "driving_license": driver.license_valid_until,
        "passport":        driver.passport_valid_until,
        "bi":              driver.bi_valid_until,
    }
    for document_type, valid_until in candidates.items():
        if valid_until is None:
            if document_type in required_for_missing:
                violations.append({"code": "missing_document", "document_type": document_type})
        elif valid_until < today:
            violations.append(
                {
                    "code": "expired_document",
                    "document_type": document_type,
                    "valid_until": valid_until.isoformat(),
                }
            )
    return violations


def driver_compliance_warnings(
    driver: Driver,
    *,
    policy: dict | None = None,
) -> list[dict]:
    policy = policy or {}
    required_documents = set(_required_documents(policy, "driver_required_documents"))
    if not required_documents:
        required_documents = {"driving_license", "passport", "bi"}

    candidates = {
        "driving_license": driver.license_valid_until,
        "passport": driver.passport_valid_until,
        "bi": driver.bi_valid_until,
    }
    warnings = []
    for document_type, valid_until in candidates.items():
        if document_type not in required_documents or valid_until is None:
            continue
        if _is_expiring_soon(valid_until, policy=policy):
            warnings.append(
                {
                    "code": "document_expiring",
                    "document_type": document_type,
                    "valid_until": valid_until.isoformat(),
                    "days_until_expiry": (valid_until - _today()).days,
                }
            )
    return warnings


async def _active_waiver_summaries(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str,
    entity_id: UUID,
) -> list[dict]:
    rows = await db.execute(
        select(OperationalWaiver).where(
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.entity_type == entity_type,
            OperationalWaiver.entity_id == entity_id,
            OperationalWaiver.status == "active",
        )
    )
    return [
        {
            "id": waiver.id,
            "waiver_type": waiver.waiver_type,
            "risk_level": waiver.risk_level,
            "reason": waiver.reason,
            "expires_at": waiver.expires_at,
            "approved_by": waiver.approved_by,
        }
        for waiver in rows.scalars()
    ]


async def _has_waivers_for_violations(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str,
    entity_id: UUID,
    violations: list[dict],
) -> bool:
    for violation in violations:
        waiver_type = (
            "missing_document"
            if violation["code"] == "missing_document"
            else "expired_warning"
        )
        if not await has_active_waiver(
            db,
            tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            waiver_type=waiver_type,
        ):
            return False
    return True


async def vehicle_availability_summary(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    *,
    exclude_trip_id: UUID | None = None,
) -> dict:
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    tenant = await db.get(Tenant, tenant_id)
    policy = _tenant_policy(tenant)
    violations = vehicle_compliance_violations(vehicle, policy=policy)
    warnings = vehicle_compliance_warnings(vehicle, policy=policy)
    compliance_blocked = bool(violations) and not await _has_waivers_for_violations(
        db,
        tenant_id,
        entity_type="vehicle",
        entity_id=vehicle.id,
        violations=violations,
    )

    active_work_order_id = await db.scalar(
        select(WorkOrder.id).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.vehicle_id == vehicle_id,
            WorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),
        )
    )

    active_trip_query = select(Trip.id).where(
        Trip.tenant_id == tenant_id,
        Trip.vehicle_id == vehicle_id,
        Trip.status.in_(ACTIVE_TRIP_STATUSES),
    )
    if exclude_trip_id:
        active_trip_query = active_trip_query.where(Trip.id != exclude_trip_id)
    active_trip_id = await db.scalar(active_trip_query)

    blockers = []
    if vehicle.status != "active":
        blockers.append({"code": "vehicle_unavailable", "vehicle_status": vehicle.status})
    if compliance_blocked:
        blockers.append({"code": "vehicle_compliance_blocked", "violations": violations})
    if active_work_order_id:
        blockers.append({"code": "vehicle_workshop_blocked", "work_order_id": active_work_order_id})
    if active_trip_id:
        blockers.append({"code": "vehicle_assignment_conflict", "trip_id": active_trip_id})

    return {
        "entity_type": "vehicle",
        "entity_id": vehicle.id,
        "status": vehicle.status,
        "available": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "compliance_violations": violations,
        "active_waivers": await _active_waiver_summaries(
            db,
            tenant_id,
            entity_type="vehicle",
            entity_id=vehicle.id,
        ),
        "active_trip_id": active_trip_id,
        "active_work_order_id": active_work_order_id,
    }


async def driver_availability_summary(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    *,
    exclude_trip_id: UUID | None = None,
) -> dict:
    driver = await db.get(Driver, driver_id)
    if not driver or driver.tenant_id != tenant_id:
        raise ApiError("driver_not_found", "Driver not found.", status_code=404)

    tenant = await db.get(Tenant, tenant_id)
    policy = _tenant_policy(tenant)
    violations = driver_compliance_violations(driver, policy=policy)
    warnings = driver_compliance_warnings(driver, policy=policy)
    compliance_blocked = bool(violations) and not await _has_waivers_for_violations(
        db,
        tenant_id,
        entity_type="driver",
        entity_id=driver.id,
        violations=violations,
    )

    active_trip_query = select(Trip.id).where(
        Trip.tenant_id == tenant_id,
        Trip.driver_id == driver_id,
        Trip.status.in_(ACTIVE_TRIP_STATUSES),
    )
    if exclude_trip_id:
        active_trip_query = active_trip_query.where(Trip.id != exclude_trip_id)
    active_trip_id = await db.scalar(active_trip_query)

    blockers = []
    if driver.status != "active":
        blockers.append({"code": "driver_unavailable", "driver_status": driver.status})
    if compliance_blocked:
        blockers.append({"code": "driver_compliance_blocked", "violations": violations})
    if active_trip_id:
        blockers.append({"code": "driver_assignment_conflict", "trip_id": active_trip_id})

    return {
        "entity_type": "driver",
        "entity_id": driver.id,
        "status": driver.status,
        "available": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "compliance_violations": violations,
        "active_waivers": await _active_waiver_summaries(
            db,
            tenant_id,
            entity_type="driver",
            entity_id=driver.id,
        ),
        "active_trip_id": active_trip_id,
    }


async def require_vehicle_available(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    *,
    exclude_trip_id: UUID | None = None,
) -> Vehicle:
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)
    if vehicle.status != "active":
        raise ApiError(
            "vehicle_unavailable",
            "Vehicle is not active for assignment.",
            status_code=status.HTTP_409_CONFLICT,
            details={"vehicle_status": vehicle.status},
        )
    tenant = await db.get(Tenant, tenant_id)
    compliance_violations = vehicle_compliance_violations(vehicle, policy=_tenant_policy(tenant))
    if compliance_violations and not await _has_waivers_for_violations(
        db,
        tenant_id,
        entity_type="vehicle",
        entity_id=vehicle.id,
        violations=compliance_violations,
    ):
        raise ApiError(
            "vehicle_compliance_blocked",
            "Vehicle has missing or expired compliance documents.",
            status_code=status.HTTP_409_CONFLICT,
            details={"violations": compliance_violations},
        )

    work_order_id = await db.scalar(
        select(WorkOrder.id).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.vehicle_id == vehicle_id,
            WorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),
        )
    )
    if work_order_id:
        raise ApiError(
            "vehicle_workshop_blocked",
            "Vehicle has an active workshop work order.",
            status_code=status.HTTP_409_CONFLICT,
            details={"work_order_id": str(work_order_id)},
        )

    conflict_query = select(Trip.id).where(
        Trip.tenant_id == tenant_id,
        Trip.vehicle_id == vehicle_id,
        Trip.status.in_(ACTIVE_TRIP_STATUSES),
    )
    if exclude_trip_id:
        conflict_query = conflict_query.where(Trip.id != exclude_trip_id)
    conflict = await db.scalar(conflict_query)
    if conflict:
        raise ApiError(
            "vehicle_assignment_conflict",
            "Vehicle already has an active trip.",
            status_code=status.HTTP_409_CONFLICT,
            details={"trip_id": str(conflict)},
        )
    return vehicle


async def require_driver_available(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    *,
    exclude_trip_id: UUID | None = None,
) -> Driver:
    driver = await db.get(Driver, driver_id)
    if not driver or driver.tenant_id != tenant_id:
        raise ApiError("driver_not_found", "Driver not found.", status_code=404)
    if driver.status != "active":
        raise ApiError(
            "driver_unavailable",
            "Driver is not active for assignment.",
            status_code=status.HTTP_409_CONFLICT,
            details={"driver_status": driver.status},
        )
    tenant = await db.get(Tenant, tenant_id)
    compliance_violations = driver_compliance_violations(driver, policy=_tenant_policy(tenant))
    if compliance_violations and not await _has_waivers_for_violations(
        db,
        tenant_id,
        entity_type="driver",
        entity_id=driver.id,
        violations=compliance_violations,
    ):
        raise ApiError(
            "driver_compliance_blocked",
            "Driver has expired compliance documents.",
            status_code=status.HTTP_409_CONFLICT,
            details={"violations": compliance_violations},
        )

    conflict_query = select(Trip.id).where(
        Trip.tenant_id == tenant_id,
        Trip.driver_id == driver_id,
        Trip.status.in_(ACTIVE_TRIP_STATUSES),
    )
    if exclude_trip_id:
        conflict_query = conflict_query.where(Trip.id != exclude_trip_id)
    conflict = await db.scalar(conflict_query)
    if conflict:
        raise ApiError(
            "driver_assignment_conflict",
            "Driver already has an active trip.",
            status_code=status.HTTP_409_CONFLICT,
            details={"trip_id": str(conflict)},
        )
    return driver


async def require_vehicle_and_driver_available(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    vehicle_id: UUID,
    driver_id: UUID,
    exclude_trip_id: UUID | None = None,
) -> tuple[Vehicle, Driver]:
    vehicle = await require_vehicle_available(
        db,
        tenant_id,
        vehicle_id,
        exclude_trip_id=exclude_trip_id,
    )
    driver = await require_driver_available(
        db,
        tenant_id,
        driver_id,
        exclude_trip_id=exclude_trip_id,
    )
    return vehicle, driver
