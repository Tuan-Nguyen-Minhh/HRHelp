"""Chat and fact-confirmation contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.agents.handoff import CaseHandoff
from src.features.answer.schema import AnswerView


class MessageView(BaseModel):
    """One stored chat row."""

    id: UUID
    role: str
    content: str
    created_at: datetime


class MessageListResponse(BaseModel):
    case_id: UUID
    conversation_id: UUID | None
    messages: list[MessageView]


class SendMessageRequest(BaseModel):
    """One user turn in the case conversation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=8000)


class FactConfirmItem(BaseModel):
    """One fact HR confirms or corrects."""

    model_config = ConfigDict(str_strip_whitespace=True)

    fact_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    fact_value: str | None = Field(default=None, max_length=4000)
    confirmed: bool = True


class ConfirmFactsRequest(BaseModel):
    """Body of ``POST /cases/{id}/facts/confirm``."""

    facts: list[FactConfirmItem] = Field(min_length=1, max_length=20)


class FactView(BaseModel):
    """A required fact, filled or still empty."""

    fact_key: str
    label: str
    fact_value: str | None
    confirmed: bool
    confidence: float | None = None


class TurnResponse(BaseModel):
    """What the chat screen renders after a message or a confirmation."""

    case_id: UUID
    case_status: str
    conversation_id: UUID
    family: str
    assistant_message: str
    facts: list[FactView]
    missing_fact_keys: list[str]
    facts_locked: bool
    answer: AnswerView | None = None
    handoff: CaseHandoff | None = None
    agent_run_id: UUID | None = None
    requested_action: str | None = None
    user_intent: str | None = None
    assessment_id: UUID | None = None


class FactListResponse(BaseModel):
    """The fact form, including values read from the narrative but not saved yet."""

    case_id: UUID
    case_status: str
    family: str
    facts: list[FactView]
    missing_fact_keys: list[str]
    facts_locked: bool
