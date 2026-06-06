from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ROTAS"
    environment: str = Field(validation_alias="ENVIRONMENT")
    api_v1_prefix: str = "/api/v1"
    version: str = "0.1.0"

    # D-04: DATABASE_URL is required — app must refuse startup if absent.
    database_url: str = Field(validation_alias="DATABASE_URL")

    # D-18: Admin DB for ARQ worker — uses rotas_admin role (BYPASSRLS)
    # Default falls back to DATABASE_URL so local dev works without two URLs
    admin_database_url: str = Field(default="", validation_alias="ADMIN_DATABASE_URL")

    # ALEMBIC_DATABASE_URL: uses rotas_admin role (BYPASSRLS) so migrations work after RLS.
    # Falls back to DATABASE_URL if not set (safe for local dev where RLS may not be active).
    alembic_database_url: str = Field(default="", validation_alias="ALEMBIC_DATABASE_URL")
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6381, validation_alias="REDIS_PORT")

    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # SEC-01 / D-03: SecretStr with no default — app raises ValidationError at startup if absent
    jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = Field(default_factory=list, validation_alias="CORS_ORIGINS")
    local_upload_dir: str = Field(default=".rotas_uploads", validation_alias="LOCAL_UPLOAD_DIR")
    redis_url: str = Field(
        default="redis://localhost:6381",
        validation_alias="REDIS_URL",
    )

    # INFRA-01: Sentry DSNs — optional, Sentry disabled if absent (D-02)
    sentry_dsn_backend: str = Field(default="", validation_alias="SENTRY_DSN_BACKEND")
    sentry_dsn_manager: str = Field(default="", validation_alias="SENTRY_DSN_MANAGER")
    sentry_dsn_driver: str = Field(default="", validation_alias="SENTRY_DSN_DRIVER")

    # INFRA-02: R2/S3 dual-provider storage (D-08)
    storage_provider: str = Field(default="local", validation_alias="STORAGE_PROVIDER")
    r2_bucket: str = Field(default="", validation_alias="R2_BUCKET")
    r2_endpoint_url: str = Field(default="", validation_alias="R2_ENDPOINT_URL")
    r2_access_key_id: str = Field(default="", validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: SecretStr = Field(default=SecretStr(""), validation_alias="R2_SECRET_ACCESS_KEY")

    # INFRA-03: Upgrade URL — drives 403 body and dashboard banner (D-16)
    upgrade_url: str = Field(default="", validation_alias="UPGRADE_URL")

    @property
    def resolved_admin_database_url(self) -> str:
        return self.admin_database_url if self.admin_database_url else self.database_url

    @property
    def resolved_alembic_database_url(self) -> str:
        return self.alembic_database_url if self.alembic_database_url else self.database_url

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        """D-05 / SEC-02: In production, CORS_ORIGINS must be explicit — no wildcard, no empty."""
        if self.environment == "production":
            if not self.cors_origins or "*" in self.cors_origins:
                raise ValueError(
                    "CORS_ORIGINS must be set to one or more explicit origins (not '*') "
                    "when ENVIRONMENT=production."
                )
            if self.redis_url == "redis://localhost:6381":
                raise ValueError(
                    "REDIS_URL must be set to a production Redis URL when ENVIRONMENT=production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
