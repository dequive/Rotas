"""Tests for driver_compliance_violations() in availability/service.py.

Pure function tests — no DB required. Uses MagicMock(spec=Driver) to build
minimal driver objects with only the fields exercised by the function.

Behaviors tested (plan 260607-o5b Task 1):
  1. Expired passport → expired_document violation for passport
  2. Expired BI → expired_document violation for bi
  3. Missing passport when required by policy → missing_document violation
  4. Expired passport + valid license → only passport violation returned
  5. All three expired → three violations returned
  6. Empty driver_required_documents in policy → defaults to {driving_license, passport, bi}
  7. All None expiry dates, no required_documents policy → returns []
"""
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.modules.availability.service import driver_compliance_violations
from app.modules.drivers.models import Driver


def _today() -> date:
    from datetime import UTC, datetime
    return datetime.now(UTC).date()


def _driver(
    license_valid_until=None,
    passport_valid_until=None,
    bi_valid_until=None,
) -> MagicMock:
    """Build a minimal Driver mock with the three expiry date fields."""
    mock = MagicMock(spec=Driver)
    mock.license_valid_until = license_valid_until
    mock.passport_valid_until = passport_valid_until
    mock.bi_valid_until = bi_valid_until
    return mock


# ---------------------------------------------------------------------------
# Test 1: Expired passport produces expired_document violation
# ---------------------------------------------------------------------------

def test_expired_passport_produces_violation():
    yesterday = _today() - timedelta(days=1)
    driver = _driver(passport_valid_until=yesterday)
    # Default policy: all three docs required
    violations = driver_compliance_violations(driver, policy={})
    codes = [(v["code"], v["document_type"]) for v in violations]
    assert ("expired_document", "passport") in codes, (
        f"Expected expired_document/passport in violations, got: {violations}"
    )


# ---------------------------------------------------------------------------
# Test 2: Expired BI produces expired_document violation
# ---------------------------------------------------------------------------

def test_expired_bi_produces_violation():
    yesterday = _today() - timedelta(days=1)
    driver = _driver(bi_valid_until=yesterday)
    violations = driver_compliance_violations(driver, policy={})
    codes = [(v["code"], v["document_type"]) for v in violations]
    assert ("expired_document", "bi") in codes, (
        f"Expected expired_document/bi in violations, got: {violations}"
    )


# ---------------------------------------------------------------------------
# Test 3: Missing passport when policy requires it → missing_document
# ---------------------------------------------------------------------------

def test_missing_passport_required_by_policy():
    driver = _driver(passport_valid_until=None, bi_valid_until=None, license_valid_until=None)
    policy = {"driver_required_documents": ["passport"]}
    violations = driver_compliance_violations(driver, policy=policy)
    codes = [(v["code"], v["document_type"]) for v in violations]
    assert ("missing_document", "passport") in codes, (
        f"Expected missing_document/passport in violations, got: {violations}"
    )


# ---------------------------------------------------------------------------
# Test 4: Valid license + expired passport → only passport violation
# ---------------------------------------------------------------------------

def test_valid_license_expired_passport_only_passport_violation():
    tomorrow = _today() + timedelta(days=1)
    yesterday = _today() - timedelta(days=1)
    driver = _driver(license_valid_until=tomorrow, passport_valid_until=yesterday)
    violations = driver_compliance_violations(driver, policy={})
    doc_types = [v["document_type"] for v in violations if v["code"] == "expired_document"]
    assert "passport" in doc_types, f"Expected passport expired_document, got: {violations}"
    assert "driving_license" not in doc_types, (
        f"Expected no driving_license violation, got: {violations}"
    )


# ---------------------------------------------------------------------------
# Test 5: All three expired → three violations
# ---------------------------------------------------------------------------

def test_all_three_expired_produces_three_violations():
    yesterday = _today() - timedelta(days=1)
    driver = _driver(
        license_valid_until=yesterday,
        passport_valid_until=yesterday,
        bi_valid_until=yesterday,
    )
    violations = driver_compliance_violations(driver, policy={})
    expired_doc_types = {
        v["document_type"] for v in violations if v["code"] == "expired_document"
    }
    assert expired_doc_types == {"driving_license", "passport", "bi"}, (
        f"Expected three expired_document violations, got: {violations}"
    )
    assert len([v for v in violations if v["code"] == "expired_document"]) == 3, (
        f"Expected exactly 3 expired violations, got: {violations}"
    )


# ---------------------------------------------------------------------------
# Test 6: Expired docs are always violations regardless of policy
# ---------------------------------------------------------------------------

def test_expired_docs_always_violate_regardless_of_policy():
    """expired_document is raised for any expired field — no policy required."""
    yesterday = _today() - timedelta(days=1)
    driver = _driver(
        license_valid_until=yesterday,
        passport_valid_until=yesterday,
        bi_valid_until=yesterday,
    )
    # Empty required_documents — but expired dates still produce violations
    policy = {"driver_required_documents": []}
    violations = driver_compliance_violations(driver, policy=policy)
    expired_doc_types = {
        v["document_type"] for v in violations if v["code"] == "expired_document"
    }
    assert expired_doc_types == {"driving_license", "passport", "bi"}, (
        f"All three expired docs should produce violations regardless of policy, got: {violations}"
    )


# ---------------------------------------------------------------------------
# Test 7: All None expiry + no policy → [] (missing_document only when policy
#          explicitly requires the document)
# ---------------------------------------------------------------------------

def test_all_none_expiry_no_policy_returns_empty():
    """With no policy and all None expiry, returns [] — missing_document requires explicit policy."""
    driver = _driver(
        license_valid_until=None,
        passport_valid_until=None,
        bi_valid_until=None,
    )
    # No required_documents in policy → missing dates are NOT violations
    # (operators can onboard drivers without all dates upfront)
    violations = driver_compliance_violations(driver, policy={})
    assert violations == [], (
        f"No policy + all None expiry should return [], got: {violations}"
    )


def test_no_required_documents_no_violations_when_not_required():
    """When policy explicitly excludes a doc type, None expiry doesn't produce violation."""
    driver = _driver(
        license_valid_until=None,
        passport_valid_until=None,
        bi_valid_until=None,
    )
    # Only driving_license required — passport and bi not required
    policy = {"driver_required_documents": ["driving_license"]}
    violations = driver_compliance_violations(driver, policy=policy)
    doc_types = {v["document_type"] for v in violations}
    assert "passport" not in doc_types, (
        f"passport not required — should not appear in violations, got: {violations}"
    )
    assert "bi" not in doc_types, (
        f"bi not required — should not appear in violations, got: {violations}"
    )
    # driving_license IS required and is None → missing_document
    assert any(
        v["code"] == "missing_document" and v["document_type"] == "driving_license"
        for v in violations
    ), f"driving_license should be missing_document, got: {violations}"
