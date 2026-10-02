"""Notification list."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationView(BaseModel):
    id: UUID
    case_id: UUID | None
    event: str
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    notifications: list[NotificationView] = Field(default_factory=list)
