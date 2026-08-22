from collections.abc import Callable
from typing import cast

import pytest
from pydantic import ValidationError

from core.config import Settings


def _settings(**values) -> Settings:
    factory = cast(Callable[..., Settings], Settings)
    return factory(_env_file=None, **values)


def _valid_values() -> dict:
    return {
        "ENVIRONMENT": "production",
        "GOVERNANCE_DATABASE_URL": (
            "postgresql+asyncpg://governance_app:secret@governance-postgres:5432/governance"
        ),
        "JWT_SECRET_KEY": "governance-jwt-secret-at-least-32-characters",
        "PLATFORM_ADMIN_KEY": "governance-platform-key-at-least-32-characters",
        "CORS_ORIGINS": [],
    }


def test_governance_production_config_accepts_internal_fail_closed_baseline():
    settings = _settings(**_valid_values())

    assert settings.environment == "production"
    assert settings.cors_origins == []


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("JWT_SECRET_KEY", "short", "JWT_SECRET_KEY"),
        ("PLATFORM_ADMIN_KEY", "short", "PLATFORM_ADMIN_KEY"),
        (
            "GOVERNANCE_DATABASE_URL",
            "postgresql+asyncpg://user:secret@localhost:5432/governance",
            "localhost",
        ),
        ("CORS_ORIGINS", ["*"], "must not contain"),
        ("CORS_ORIGINS", ["http://governance.example"], "HTTPS"),
    ],
)
def test_governance_production_config_rejects_unsafe_values(key, value, message):
    values = _valid_values()
    values[key] = value

    with pytest.raises((ValidationError, ValueError), match=message):
        _settings(**values)
