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


async def test_production_local_storage_raises(monkeypatch):
    """INFRA-02: Public production must use durable object storage."""
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-at-least-32-chars-long-abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.rotas.co.mz"]')
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    with pytest.raises((ValidationError, ValueError)):
        from app.config import Settings
        Settings(_env_file=None)


async def test_production_r2_requires_all_settings(monkeypatch):
    """INFRA-02: R2 mode must fail closed when credentials are incomplete."""
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-at-least-32-chars-long-abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.rotas.co.mz"]')
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379")
    monkeypatch.setenv("STORAGE_PROVIDER", "r2")
    monkeypatch.setenv("R2_BUCKET", "rotas-prod")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    with pytest.raises((ValidationError, ValueError)):
        from app.config import Settings
        Settings(_env_file=None)


async def test_production_requires_transactional_email(monkeypatch):
    """SELF-01: Public production must have a transactional email path."""
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-at-least-32-chars-long-abc")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://rotas:rotas@localhost:55432/rotas")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.rotas.co.mz"]')
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379")
    monkeypatch.setenv("STORAGE_PROVIDER", "r2")
    monkeypatch.setenv("R2_BUCKET", "rotas-prod")
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "access-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setenv("EMAIL_PROVIDER", "none")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "suporte@rotas.co.mz")
    monkeypatch.setenv("MANAGER_PUBLIC_URL", "https://app.rotas.co.mz")
    with pytest.raises((ValidationError, ValueError)):
        from app.config import Settings
        Settings(_env_file=None)
