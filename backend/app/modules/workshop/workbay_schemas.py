from uuid import UUID
from pydantic import BaseModel


class WorkBayCreate(BaseModel):
    name: str
    category: str = "geral"
    is_active: bool = True


class WorkBayUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None
