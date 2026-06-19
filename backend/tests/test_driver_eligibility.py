"""Tests for check_driver_eligibility — pure function, no DB.

Test cases:
  1. test_all_clear_eligible — active driver, all dates 90 days in future → is_eligible=True
  2. test_suspended_driver_not_eligible — status='suspended', dates all valid → is_eligible=False
  3. test_expired_license_not_eligible — license_valid_until in the past → is_eligible=False
  4. test_expired_bi_not_eligible — bi_valid_until in the past → is_eligible=False
  5. test_expired_passport_not_eligible — passport_valid_until in the past → is_eligible=False
  6. test_expiring_soon_warning — license expires in 15 days → is_eligible=True, expiring_soon populated
  7. test_none_dates_skipped — all date fields None → is_eligible=True (no doc on file = not blocking)
  8. test_custom_reference_date — pass reference_date explicitly; future date becomes past relative to reference
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

from app.modules.third_party.eligibility import check_driver_eligibility

REF = date(2026, 6, 19)  # fixed reference date for deterministic tests


def make_driver(**overrides):
    """Create a mock Driver with all-valid defaults."""
    driver = MagicMock()
    driver.status = "active"
    driver.license_valid_until = REF + timedelta(days=90)
    driver.passport_valid_until = REF + timedelta(days=90)
    driver.bi_valid_until = REF + timedelta(days=90)
    for k, v in overrides.items():
        setattr(driver, k, v)
    return driver


def test_all_clear_eligible():
    driver = make_driver()
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is True
    assert result.blocking_reasons == []
    assert result.expiring_soon == []
    assert result.checked_at == REF


def test_suspended_driver_not_eligible():
    driver = make_driver(status="suspended")
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is False
    assert any("suspended" in r for r in result.blocking_reasons)


def test_expired_license_not_eligible():
    driver = make_driver(license_valid_until=REF - timedelta(days=1))
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is False
    assert any("driver_license" in r for r in result.blocking_reasons)


def test_expired_bi_not_eligible():
    driver = make_driver(bi_valid_until=REF - timedelta(days=10))
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is False
    assert any("bi" in r for r in result.blocking_reasons)


def test_expired_passport_not_eligible():
    driver = make_driver(passport_valid_until=REF - timedelta(days=5))
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is False
    assert any("passport" in r for r in result.blocking_reasons)


def test_expiring_soon_warning():
    driver = make_driver(license_valid_until=REF + timedelta(days=15))
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is True  # warning, NOT blocking
    assert result.blocking_reasons == []
    assert any("driver_license" in w for w in result.expiring_soon)


def test_none_dates_skipped():
    driver = make_driver(
        license_valid_until=None,
        passport_valid_until=None,
        bi_valid_until=None,
    )
    result = check_driver_eligibility(driver, reference_date=REF)
    assert result.is_eligible is True
    assert result.blocking_reasons == []
    assert result.expiring_soon == []


def test_custom_reference_date():
    """A license date that's in the future relative to REF becomes expired
    relative to a reference_date far in the future."""
    future_license = REF + timedelta(days=10)  # expires 10 days after REF
    far_future_ref = REF + timedelta(days=20)  # reference is 20 days after REF
    driver = make_driver(license_valid_until=future_license)
    result = check_driver_eligibility(driver, reference_date=far_future_ref)
    assert result.is_eligible is False
    assert any("driver_license" in r for r in result.blocking_reasons)
