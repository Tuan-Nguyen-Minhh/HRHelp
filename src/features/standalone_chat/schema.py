"""Chat contracts without a case or fact/workflow payload."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from src.features.clarify.schema import MessageView, SendMessageRequest


class StandaloneMessageRequest(SendMessageRequest):
    conversation_id: UUID | None = None
    lookup_date: date | None = None


class ConversationView(BaseModel):
    id: UUID
    title: str
    updated_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationView]


class StandaloneMessagesResponse(BaseModel):
    conversation_id: UUID
    messages: list[MessageView]


class StandaloneTurnResponse(StandaloneMessagesResponse):
    agent_run_id: UUID
    reply_kind: str
    lookup_date: date
