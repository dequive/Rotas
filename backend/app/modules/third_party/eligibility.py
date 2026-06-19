"""
Operational eligibility service for drivers.

Pure domain check — no DB calls, no async. Reads existing Driver fields
(license_valid_until, passport_valid_until, bi_valid_until, status) and
returns an EligibilityResult with blocking reasons and expiring-soon warnings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.drivers.models import Driver

EXPIRY_WARNING_DAYS = 30


@dataclass
class EligibilityResult:
    """Result of a driver eligibility check.

    Attributes:
        is_eligible: True when no blocking conditions were found.
        blocking_reasons: Human-readable list of conditions that make the driver ineligible.
        expiring_soon: Human-readable list of documents expiring within EXPIRY_WARNING_DAYS.
        checked_at: The reference date the check was evaluated against.
    """

    is_eligible: bool
    blocking_reasons: list[str] = field(default_factory=list)
    expiring_soon: list[str] = field(default_factory=list)
    checked_at: date = field(default_factory=date.today)


def check_driver_eligibility(
    driver: "Driver",
    reference_date: date | None = None,
) -> EligibilityResult:
    """Pure domain check — no DB calls.

    Reads existing Driver fields:
    - status: must be 'active'
    - license_valid_until: must not be expired as of reference_date
    - passport_valid_until: must not be expired as of reference_date
    - bi_valid_until: must not be expired as of reference_date

    Args:
        driver: Driver ORM instance (or any object with the required attributes).
        reference_date: Date to evaluate expiry against. Defaults to date.today().

    Returns:
        EligibilityResult with is_eligible, blocking_reasons, expiring_soon, checked_at.
    """
    if reference_date is None:
        reference_date = date.today()

    blocking: list[str] = []
    expiring: list[str] = []

    if driver.status != "active":
        blocking.append(f"driver status is '{driver.status}'")

    _check_date(driver.license_valid_until, "driver_license", reference_date, blocking, expiring)
    _check_date(driver.passport_valid_until, "passport", reference_date, blocking, expiring)
    _check_date(driver.bi_valid_until, "bi", reference_date, blocking, expiring)

    return EligibilityResult(
        is_eligible=len(blocking) == 0,
        blocking_reasons=blocking,
        expiring_soon=expiring,
        checked_at=reference_date,
    )


def _check_date(
    expiry: date | None,
    field_name: str,
    reference_date: date,
    blocking: list[str],
    expiring: list[str],
) -> None:
    """Append to blocking or expiring based on how close expiry is to reference_date."""
    if expiry is None:
        return  # document not on file — not a blocking condition

    if expiry < reference_date:
        blocking.append(f"{field_name} expired on {expiry}")
    elif (expiry - reference_date).days <= EXPIRY_WARNING_DAYS:
        expiring.append(f"{field_name} expires on {expiry}")
