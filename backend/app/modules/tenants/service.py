from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.tenants.models import Tenant
from app.modules.tenants.schemas import DriverDespachoTableUpdate, TenantPatch

DRIVER_DESPACHO_TABLE_KEY = "driver_travel_allowance_policy"


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def serialize_tenant(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "max_vehicles": tenant.max_vehicles,
        "max_drivers": tenant.max_drivers,
        "max_users": tenant.max_users,
        "is_active": tenant.is_active,
        "is_trial": tenant.is_trial,
        "trial_ends_at": tenant.trial_ends_at,
        "whatsapp_number": tenant.whatsapp_number,
        "timezone": tenant.timezone,
        "currency": tenant.currency,
        "compliance_policy": tenant.compliance_policy,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at,
    }


async def get_current_tenant(db: AsyncSession, tenant_id: UUID) -> dict:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise ApiError(
            "tenant_not_found",
            "Tenant not found or inactive.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return serialize_tenant(tenant)


async def patch_current_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    payload: TenantPatch,
    *,
    actor_id: UUID | None = None,
) -> dict:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise ApiError(
            "tenant_not_found",
            "Tenant not found or inactive.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    values = payload.model_dump(exclude_unset=True)
    if "currency" in values and values["currency"]:
        values["currency"] = values["currency"].upper()
        if len(values["currency"]) != 3:
            raise ApiError(
                "invalid_currency",
                "Currency must be a 3-letter code.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
    if "compliance_policy" in values and values["compliance_policy"] is not None:
        _validate_compliance_policy(values["compliance_policy"])

    old_values = serialize_tenant(tenant)
    for field, value in values.items():
        setattr(tenant, field, value)
    await db.flush()
    await db.refresh(tenant)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="tenant.updated",
        entity_type="tenant",
        entity_id=tenant.id,
        old_values=old_values,
        new_values=serialize_tenant(tenant),
    )
    await db.commit()
    await db.refresh(tenant)
    return serialize_tenant(tenant)


async def get_driver_despacho_table(db: AsyncSession, tenant_id: UUID) -> dict:
    tenant = await _require_active_tenant(db, tenant_id)
    policy = tenant.compliance_policy or {}
    table = policy.get(DRIVER_DESPACHO_TABLE_KEY)
    return {
        "configured": isinstance(table, dict),
        "table": table if isinstance(table, dict) else None,
    }


async def put_driver_despacho_table(
    db: AsyncSession,
    tenant_id: UUID,
    payload: DriverDespachoTableUpdate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    tenant = await _require_active_tenant(db, tenant_id)
    table = payload.model_dump(exclude_none=True)
    table["currency"] = table["currency"].upper()
    table["entry_mode"] = "manual"
    policy = dict(tenant.compliance_policy or {})
    old_values = serialize_tenant(tenant)
    policy[DRIVER_DESPACHO_TABLE_KEY] = table
    _validate_compliance_policy(policy)
    tenant.compliance_policy = policy
    await db.flush()
    await db.refresh(tenant)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="tenant.driver_despacho_table.updated",
        entity_type="tenant",
        entity_id=tenant.id,
        old_values=old_values,
        new_values={
            "driver_despacho_table": table,
            "entry_mode": "manual",
        },
    )
    await db.commit()
    await db.refresh(tenant)
    return {
        "configured": True,
        "table": tenant.compliance_policy[DRIVER_DESPACHO_TABLE_KEY],
    }


async def _require_active_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise ApiError(
            "tenant_not_found",
            "Tenant not found or inactive.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return tenant


def _validate_compliance_policy(policy: dict) -> None:
    for key in (
        "vehicle_required_documents",
        "driver_required_documents",
        "cargo_required_documents",
        "trip_required_stops",
    ):
        value = policy.get(key)
        if value is not None and (
            not isinstance(value, list) or any(not isinstance(item, str) for item in value)
        ):
            raise ApiError(
                "invalid_compliance_policy",
                "Compliance policy document lists must contain only strings.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"field": key},
            )

    for key in ("cargo_required_documents_by_type", "trip_required_stops_by_cargo_type"):
        by_cargo_type = policy.get(key)
        if by_cargo_type is None:
            continue
        if not isinstance(by_cargo_type, dict):
            raise ApiError(
                "invalid_compliance_policy",
                "Cargo type policies must map cargo types to string lists.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                details={"field": key},
            )
        for cargo_type, items in by_cargo_type.items():
            if (
                not isinstance(cargo_type, str)
                or not isinstance(items, list)
                or any(not isinstance(item, str) for item in items)
            ):
                raise ApiError(
                    "invalid_compliance_policy",
                    "Cargo type policy entries must contain only string lists.",
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    details={"field": key},
                )

    allowance_policy = policy.get(DRIVER_DESPACHO_TABLE_KEY)
    if allowance_policy is None:
        return
    if not isinstance(allowance_policy, dict):
        raise ApiError(
            "invalid_compliance_policy",
            "Driver travel allowance policy must be an object.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"field": "driver_travel_allowance_policy"},
        )
    enabled = allowance_policy.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise ApiError(
            "invalid_compliance_policy",
            "Driver travel allowance enabled flag must be boolean.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"field": "driver_travel_allowance_policy.enabled"},
        )
    currency = allowance_policy.get("currency")
    if currency is not None and (
        not isinstance(currency, str) or len(currency.strip().upper()) != 3
    ):
        raise ApiError(
            "invalid_compliance_policy",
            "Driver travel allowance currency must be a 3-letter code.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"field": "driver_travel_allowance_policy.currency"},
        )
    min_long_course_km = allowance_policy.get("min_long_course_km")
    if min_long_course_km is not None and (
        not _is_number(min_long_course_km) or min_long_course_km < 0
    ):
        raise ApiError(
            "invalid_compliance_policy",
            "Driver travel allowance minimum long-course distance must be numeric.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"field": "driver_travel_allowance_policy.min_long_course_km"},
        )
    tiers = allowance_policy.get("tiers")
    if tiers is None:
        return
    if not isinstance(tiers, list):
        raise ApiError(
            "invalid_compliance_policy",
            "Driver travel allowance tiers must include numeric min_km and amount values.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"field": "driver_travel_allowance_policy.tiers"},
        )
    for index, item in enumerate(tiers):
        if (
            not isinstance(item, dict)
            or "min_km" not in item
            or "amount" not in item
            or not _is_number(item["min_km"])
            or not _is_number(item["amount"])
            or ("max_km" in item and not _is_number(item["max_km"]))
        ):
            raise ApiError(
                "invalid_compliance_policy",
                "Driver travel allowance tiers must include numeric min_km and amount values.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                details={"field": f"driver_travel_allowance_policy.tiers.{index}"},
            )
        if item["min_km"] < 0 or item["amount"] < 0:
            raise ApiError(
                "invalid_compliance_policy",
                "Driver travel allowance tier distances and amounts cannot be negative.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                details={"field": f"driver_travel_allowance_policy.tiers.{index}"},
            )
        if "max_km" in item and item["max_km"] <= item["min_km"]:
            raise ApiError(
                "invalid_compliance_policy",
                "Driver travel allowance tier max_km must be greater than min_km.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                details={"field": f"driver_travel_allowance_policy.tiers.{index}.max_km"},
            )
