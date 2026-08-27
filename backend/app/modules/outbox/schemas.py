from typing import Literal

from pydantic import BaseModel, Field


class OutboxReplayRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class OutboxReplayResponse(BaseModel):
    replayed: bool
    event: dict


OutboxStatus = Literal["pending", "sent", "dead_letter"]
