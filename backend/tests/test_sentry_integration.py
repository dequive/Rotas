"""Tests for INFRA-01: Sentry PII scrubber and init guard."""
import pytest

# Will import from app.main once _scrub_pii is defined there
# from app.main import _scrub_pii


@pytest.mark.skip(reason="Wave 1 — _scrub_pii not yet implemented in main.py")
def test_scrub_pii_strips_all_fields():
    """_scrub_pii removes driver_name, cargo_description, phone, nuit, email,
    plate_number, receiver_name, receiver_contact from event extras."""
    pass


@pytest.mark.skip(reason="Wave 1 — _scrub_pii not yet implemented in main.py")
def test_scrub_pii_handles_nested_dict():
    """_scrub_pii recursively strips PII fields nested inside dicts."""
    pass


@pytest.mark.skip(reason="Wave 1 — _scrub_pii not yet implemented in main.py")
def test_scrub_sql_breadcrumbs():
    """_scrub_pii removes 'data' key from breadcrumbs with category='query'."""
    pass


@pytest.mark.skip(reason="Wave 1 — _scrub_pii not yet implemented in main.py")
def test_sentry_not_initialized_without_dsn(monkeypatch):
    """sentry_sdk.init is never called when SENTRY_DSN_BACKEND is empty."""
    pass
