from uuid import UUID

from pydantic import BaseModel, Field

from core.schemas import Severity


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9\-]+$")


class CreateApiKeyRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    scopes: list[str] = Field(..., min_length=1)
    expires_in_days: int | None = Field(None, ge=1, le=3650)


class CreateDomainRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9._\-]+$")
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None


class CreateCaseTypeRequest(BaseModel):
    domain_id: UUID
    code: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9._\-]+$")
    name: str = Field(..., min_length=1, max_length=120)
    initial_status: str = Field("open", min_length=1, max_length=50)
    sla_hours: int | None = Field(None, ge=1)


class CreateTypeRequest(BaseModel):
    domain_id: UUID
    code: str = Field(..., min_length=1, max_length=60, pattern=r"^[a-z0-9._\-]+$")
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None


class CreatePromotionRequest(BaseModel):
    type_id: UUID
    case_type_id: UUID
    min_severity: Severity = "alta"


class CreateTransitionRuleRequest(BaseModel):
    case_type_id: UUID
    from_status: str | None = Field(None, max_length=50)
    to_status: str = Field(..., min_length=1, max_length=50)
    required_fields: list[str] = Field(default_factory=list)
    required_attachments: bool = False
    sla_hours: int | None = Field(None, ge=1)
