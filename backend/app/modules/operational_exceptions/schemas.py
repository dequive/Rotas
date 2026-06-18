from pydantic import BaseModel


class ResolveExceptionRequest(BaseModel):
    resolution_notes: str
