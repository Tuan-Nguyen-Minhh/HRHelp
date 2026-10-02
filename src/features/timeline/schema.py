"""One row on the case timeline."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    at: datetime
    kind: str
    label: str
    entity_type: str | None = None
    entity_id: UUID | None = None


class TimelineResponse(BaseModel):
    case_id: UUID
    events: list[TimelineEvent] = Field(default_factory=list)
