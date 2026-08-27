"""Fail-closed protection for mutable tests that require PostgreSQL."""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

_DISPOSABLE_DATABASE_NAME = re.compile(r"^rotas_test_[a-z0-9_]+$")
_DEFAULT_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_OPERATIONAL_URL_VARIABLES = (
    "DATABASE_URL",
    "ADMIN_DATABASE_URL",
    "ALEMBIC_DATABASE_URL",
)


class TestDatabaseConfigurationError(RuntimeError):
    """Raised before test collection when the database target is unsafe."""

    __test__ = False


def _parse_database_url(raw_url: str, variable_name: str) -> URL:
    try:
        url = make_url(raw_url)
    except (ArgumentError, TypeError, ValueError) as exc:
        raise TestDatabaseConfigurationError(
            f"{variable_name} must be a valid PostgreSQL URL."
        ) from exc

    if not url.drivername.startswith("postgresql"):
        raise TestDatabaseConfigurationError(f"{variable_name} must use PostgreSQL.")
    if not url.host:
        raise TestDatabaseConfigurationError(f"{variable_name} must include an explicit host.")
    if not url.database:
        raise TestDatabaseConfigurationError(f"{variable_name} must include a database name.")
    return url


def _normalized_host(url: URL) -> str:
    assert url.host is not None
    return url.host.rstrip(".").lower()


def _physical_target(url: URL) -> tuple[str, int, str]:
    assert url.database is not None
    return (_normalized_host(url), url.port or 5432, url.database)


def _allowed_hosts(environment: Mapping[str, str]) -> frozenset[str]:
    configured = environment.get("TEST_DATABASE_ALLOWED_HOSTS", "")
    additional = {
        host.strip().rstrip(".").lower()
        for host in configured.split(",")
        if host.strip()
    }
    return _DEFAULT_ALLOWED_HOSTS | additional


def validate_test_database_url(environment: Mapping[str, str]) -> str:
    """Return the safe test URL or raise without disclosing credentials."""
    raw_test_url = environment.get("TEST_DATABASE_URL", "").strip()
    if not raw_test_url:
        raise TestDatabaseConfigurationError(
            "TEST_DATABASE_URL is required before collecting mutable backend tests."
        )

    test_url = _parse_database_url(raw_test_url, "TEST_DATABASE_URL")
    if _normalized_host(test_url) not in _allowed_hosts(environment):
        raise TestDatabaseConfigurationError(
            "TEST_DATABASE_URL host is outside TEST_DATABASE_ALLOWED_HOSTS allowlist."
        )

    database_name = test_url.database or ""
    if _DISPOSABLE_DATABASE_NAME.fullmatch(database_name) is None:
        raise TestDatabaseConfigurationError(
            "TEST_DATABASE_URL database name must match rotas_test_* using lowercase "
            "letters, digits, or underscores."
        )

    test_target = _physical_target(test_url)
    for variable_name in _OPERATIONAL_URL_VARIABLES:
        raw_operational_url = environment.get(variable_name, "").strip()
        if not raw_operational_url:
            continue
        operational_url = _parse_database_url(raw_operational_url, variable_name)
        if _physical_target(operational_url) == test_target:
            raise TestDatabaseConfigurationError(
                "TEST_DATABASE_URL must not resolve to an operational database target."
            )

    return raw_test_url


def activate_test_database(environment: MutableMapping[str, str]) -> str:
    """Validate and bind all application database roles to the disposable DB."""
    test_database_url = validate_test_database_url(environment)
    for variable_name in _OPERATIONAL_URL_VARIABLES:
        environment[variable_name] = test_database_url
    return test_database_url
