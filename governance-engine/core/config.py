from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://governance_app:governance@localhost:55433/governance",
        validation_alias="GOVERNANCE_DATABASE_URL",
    )
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    jwt_secret_key: str = Field(default="change-me-in-env", validation_alias="JWT_SECRET_KEY")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8001"],
        validation_alias="CORS_ORIGINS",
    )
    idempotency_key_max_len: int = 256
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Platform admin key — used to call /platform/onboard (tenant provisioning).
    # Must be set to a strong random value in production. Never exposed in API responses.
    platform_admin_key: SecretStr = Field(
        default=SecretStr("dev-platform-key-change-me"),
        validation_alias="PLATFORM_ADMIN_KEY",
    )

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if self.environment == "production":
            if (
                self.platform_admin_key.get_secret_value() == "dev-platform-key-change-me"
                or len(self.platform_admin_key.get_secret_value()) < 32
            ):
                raise ValueError(
                    "PLATFORM_ADMIN_KEY must contain at least 32 non-default characters "
                    "in production."
                )
            if self.jwt_secret_key == "change-me-in-env" or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must contain at least 32 non-default characters "
                    "in production."
                )
            if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
                raise ValueError(
                    "GOVERNANCE_DATABASE_URL must not use localhost in production."
                )
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not contain '*' in production.")
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError(
                    "Every Governance CORS origin must use HTTPS in production."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
