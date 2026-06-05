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
