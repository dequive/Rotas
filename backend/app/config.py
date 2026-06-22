from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]


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
    audit_log_retention_days: int = Field(
        default=365,
        validation_alias="AUDIT_LOG_RETENTION_DAYS",
    )

    # SEC-01 / D-03: SecretStr with no default — app raises ValidationError at startup if absent
    jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = Field(
        default_factory=lambda: DEV_CORS_ORIGINS.copy(),
        validation_alias="CORS_ORIGINS",
    )
    dev_test_token: SecretStr = Field(default=SecretStr(""), validation_alias="DEV_TEST_TOKEN")
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
    r2_secret_access_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="R2_SECRET_ACCESS_KEY",
    )

    # INFRA-03: Upgrade URL — drives 403 body and dashboard banner (D-16)
    upgrade_url: str = Field(default="", validation_alias="UPGRADE_URL")

    # Self-service transactional messaging.
    manager_public_url: str = Field(
        default="http://localhost:3000",
        validation_alias="MANAGER_PUBLIC_URL",
    )
    email_provider: str = Field(default="none", validation_alias="EMAIL_PROVIDER")
    email_from_address: str = Field(default="", validation_alias="EMAIL_FROM_ADDRESS")
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: SecretStr = Field(default=SecretStr(""), validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")

    # Governance Engine — optional; integration is a no-op when absent
    governance_engine_url: str = Field(default="", validation_alias="GOVERNANCE_ENGINE_URL")
    governance_api_key: str = Field(default="", validation_alias="GOVERNANCE_API_KEY")

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
            if (
                not self.cors_origins
                or "*" in self.cors_origins
                or self.cors_origins == DEV_CORS_ORIGINS
            ):
                raise ValueError(
                    "CORS_ORIGINS must be set to one or more explicit origins (not '*') "
                    "when ENVIRONMENT=production."
                )
            if self.redis_url == "redis://localhost:6381":
                raise ValueError(
                    "REDIS_URL must be set to a production Redis URL when ENVIRONMENT=production."
                )
            if self.storage_provider.lower() != "r2":
                raise ValueError(
                    "STORAGE_PROVIDER must be set to 'r2' when ENVIRONMENT=production."
                )
            missing_r2 = [
                name
                for name, value in {
                    "R2_BUCKET": self.r2_bucket,
                    "R2_ENDPOINT_URL": self.r2_endpoint_url,
                    "R2_ACCESS_KEY_ID": self.r2_access_key_id,
                    "R2_SECRET_ACCESS_KEY": self.r2_secret_access_key.get_secret_value(),
                }.items()
                if not value
            ]
            if missing_r2:
                raise ValueError(
                    "R2 storage settings are required when ENVIRONMENT=production: "
                    + ", ".join(missing_r2)
                )
            if self.email_provider.lower() == "none":
                raise ValueError("EMAIL_PROVIDER must be configured when ENVIRONMENT=production.")
            if not self.email_from_address:
                raise ValueError(
                    "EMAIL_FROM_ADDRESS must be configured when ENVIRONMENT=production."
                )
            if not self.manager_public_url.startswith("https://"):
                raise ValueError(
                    "MANAGER_PUBLIC_URL must be an HTTPS URL when ENVIRONMENT=production."
                )
            if self.email_provider.lower() == "smtp" and not self.smtp_host:
                raise ValueError(
                    "SMTP_HOST must be configured when EMAIL_PROVIDER=smtp in production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
