from pydantic import BaseModel, Field


class EmailNotificationCreate(BaseModel):
    request_reference: str = Field(min_length=1, max_length=160)
    recipient: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    body_text: str = Field(min_length=1)
    body_html: str | None = None
    template: str | None = Field(default=None, max_length=80)
    payload: dict | None = None
