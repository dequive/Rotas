import pytest
from pydantic import ValidationError

from app.config import get_settings


@pytest.fixture(autouse=True)
async def reset_settings_cache():
    yield
    get_settings.cache_clear()


async def test_missing_jwt_secret_raises_validation_error(monkeypatch):
    """SEC-01: App must refuse to start if JWT_SECRET_KEY is absent."""
    get_settings.cache_clear()
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises((ValidationError, SystemExit)):
        from app.config import Settings
        Settings(_env_file=None)


async def test_missing_environment_raises_validation_error(monkeypatch):
    """DEPLOY-01: App must refuse to start if ENVIRONMENT is absent."""
    get_settings.cache_clear()
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-at-least-32-chars-long-abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    with pytest.raises((ValidationError, SystemExit)):
        from app.config import Settings
        Settings(_env_file=None)


async def test_production_cors_origins_empty_raises(monkeypatch):
    """DEPLOY-01 + SEC-02: Production startup must reject empty CORS_ORIGINS."""
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-at-least-32-chars-long-abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises((ValidationError, ValueError)):
        from app.config import Settings
        Settings(_env_file=None)


async def test_production_cors_wildcard_raises(monkeypatch):
    """SEC-02: Production startup must reject CORS_ORIGINS containing '*'."""
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-at-least-32-chars-long-abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')
    with pytest.raises((ValidationError, ValueError)):
        from app.config import Settings
        Settings(_env_file=None)
