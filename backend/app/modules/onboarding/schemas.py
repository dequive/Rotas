from uuid import UUID

from pydantic import BaseModel, field_validator


class OnboardingRegisterRequest(BaseModel):
    company_name: str
    owner_full_name: str
    owner_email: str
    owner_password: str
    company_slug: str | None = None
    company_nuit: str | None = None
    phone: str | None = None
    timezone: str = "Africa/Maputo"
    currency: str = "MZN"
    product_modules: list[str] = ["tms"]

    @field_validator("product_modules")
    @classmethod
    def validate_product_modules(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one product module must be selected.")
        allowed = {"tms", "oficina"}
        invalid = set(value) - allowed
        if invalid:
            raise ValueError(
                f"Invalid product module(s): {sorted(invalid)}. Allowed: {sorted(allowed)}."
            )
        return sorted(list(set(value)))

    @field_validator("company_name", "owner_full_name")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field is required.")
        return cleaned

    @field_validator("owner_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or "." not in email.rsplit("@", maxsplit=1)[-1]:
            raise ValueError("A valid email is required.")
        return email

    @field_validator("owner_password")
    @classmethod
    def strong_enough_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        currency = value.strip().upper()
        if len(currency) != 3:
            raise ValueError("Currency must be a 3-letter ISO code.")
        return currency


class OnboardingTenant(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    product_modules: list[str] = ["tms"]
    trial_ends_at: str | None


class OnboardingOwner(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    email_verified_at: str | None = None


class OnboardingRegisterResponse(BaseModel):
    tenant: OnboardingTenant
    owner: OnboardingOwner
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    verification_token: str | None = None
    verification_url: str | None = None


class EmailVerificationRequest(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def non_empty_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("Verification token is required.")
        return token
