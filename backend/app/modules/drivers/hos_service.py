"""Hours of Service (HOS) calculation service.

Calculates driving hours for a driver from trip records and determines
whether they are within safe operating limits (Mozambique logistics context).

Thresholds:
  - Warning:   >= 8h driven today
  - Violation: >= 9h driven today OR >= 48h driven this week
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trips.models import Trip

HOS_WARNING_HOURS_DAY: float = 8.0
HOS_VIOLATION_HOURS_DAY: float = 9.0
HOS_VIOLATION_HOURS_WEEK: float = 48.0

_DRIVING_STATUSES = ("in_progress", "completed")


def _week_start(target_date: date) -> datetime:
    """Return Monday 00:00:00 UTC of the ISO week containing target_date."""
    monday = target_date - timedelta(days=target_date.weekday())
    return datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=UTC)


async def calculate_driving_hours(
    driver_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
    *,
    target_date: date | None = None,
) -> dict:
    """Calculate HOS hours for a driver on a given date and its ISO week.

    Args:
        driver_id: UUID of the driver to check.
        tenant_id: UUID of the tenant (enforces multitenancy isolation).
        db: Async SQLAlchemy session.
        target_date: Date to evaluate (defaults to today UTC).

    Returns:
        {
            "hours_today": float,
            "hours_this_week": float,
            "status": "ok" | "warning" | "violation",
            "violation_reason": "daily_limit" | "weekly_limit" | None,
        }
    """
    today = target_date or datetime.now(UTC).date()
    week_start = _week_start(today)
    now = datetime.now(UTC)

    # Fetch all relevant trips for the current ISO week in a single query.
    # Trips with NULL actual_departure are excluded by the IS NOT NULL filter.
    rows = await db.execute(
        select(Trip.actual_departure, Trip.actual_arrival, Trip.status).where(
            Trip.driver_id == driver_id,
            Trip.tenant_id == tenant_id,
            Trip.status.in_(_DRIVING_STATUSES),
            Trip.actual_departure.isnot(None),
            Trip.actual_departure >= week_start,
        )
    )
    trips = rows.all()

    hours_today = 0.0
    hours_this_week = 0.0

    for departure, arrival, _trip_status in trips:
        # Normalise to UTC for naive timestamps stored without tzinfo
        if departure.tzinfo is None:
            departure = departure.replace(tzinfo=UTC)

        # In-progress trips: use current time as the end
        end = arrival if arrival is not None else now
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        duration_hours = max(0.0, (end - departure).total_seconds() / 3600)
        hours_this_week += duration_hours

        # Only count toward today if the trip departed on target_date (UTC)
        if departure.date() == today:
            hours_today += duration_hours

    # Determine status — daily limit takes priority over weekly limit
    if hours_today >= HOS_VIOLATION_HOURS_DAY:
        status_val = "violation"
        violation_reason: str | None = "daily_limit"
    elif hours_this_week >= HOS_VIOLATION_HOURS_WEEK:
        status_val = "violation"
        violation_reason = "weekly_limit"
    elif hours_today >= HOS_WARNING_HOURS_DAY:
        status_val = "warning"
        violation_reason = None
    else:
        status_val = "ok"
        violation_reason = None

    return {
        "hours_today": round(hours_today, 2),
        "hours_this_week": round(hours_this_week, 2),
        "status": status_val,
        "violation_reason": violation_reason,
    }
