"""Structured decision from the clarify planner.

The model fills this object. It does not name a LangGraph edge.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CaseFamily(StrEnum):
    """Fact set the catalog already knows."""

    UNAUTHORIZED_ABSENCE = "UNAUTHORIZED_ABSENCE"
    LATE = "LATE"
    GENERAL = "GENERAL"


class UserIntent(StrEnum):
    """What the user is doing in this clarification turn."""

    PROVIDE_FACTS = "provide_facts"
    CONFIRM_FACTS = "confirm_facts"
    CORRECT_FACTS = "correct_facts"
    ASK_QUESTION = "ask_question"
    REQUEST_CONSULTATION = "request_consultation"
    CONTINUE = "continue"
    UNKNOWN = "unknown"


class RequestedAction(StrEnum):
    """Semantic hint. Python maps this to an edge after validation."""

    NEED_CLARIFICATION = "need_clarification"
    COMPLETE_FACTS = "complete_facts"
    REQUEST_RETRIEVAL = "request_retrieval"
    ANSWER_POLICY_QUESTION = "answer_policy_question"
    DRAFT_MINUTES = "draft_minutes"
    CREATE_TICKET_PREVIEW = "create_ticket_preview"
    SHOW_ASSESSMENT = "show_assessment"
    SEND_TO_LEGAL = "send_to_legal"
    UNSUPPORTED = "unsupported"


class ExtractedFact(BaseModel):
    """One catalog fact the planner read from the message."""

    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Fact key from the supplied catalog.")
    value: str = Field(description="Canonical value. Empty when the message is ambiguous.")
    confidence: float = Field(ge=0, le=1, description="Confidence that the message supports this value.")
    evidence: str = Field(description="Short span from the user message that supports the value.")
    ambiguous: bool = Field(description="True when the message does not support one value.")


class ConfirmationUpdate(BaseModel):
    """Whether the user confirmed a fact that is already stored."""

    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Catalog fact key.")
    confirmed: bool = Field(description="True only when the user explicitly confirms the stored value.")


class ClarifyDecision(BaseModel):
    """Semantic plan for one clarify turn."""

    model_config = ConfigDict(extra="ignore")

    family: CaseFamily = Field(description="Case family from the catalog. Do not invent a family.")
    family_confidence: float = Field(ge=0, le=1, description="Confidence in the family choice.")
    extracted_facts: list[ExtractedFact] = Field(
        default_factory=list,
        description="Facts stated in this message. A new fact is not confirmation.",
    )
    confirmation_updates: list[ConfirmationUpdate] = Field(
        default_factory=list,
        description="Explicit confirmation of a value already stored.",
    )
    corrections: list[ExtractedFact] = Field(
        default_factory=list,
        description="Values the user is changing. A correction of a confirmed fact is not itself acceptance.",
    )
    user_intent: UserIntent = Field(description="What the user is doing in this turn.")
    requested_action: RequestedAction = Field(description="Semantic next step. Python decides the graph edge.")
    ambiguities: list[str] = Field(
        default_factory=list,
        description="Facts the message left unclear. Do not resolve them.",
    )
    confidence: float = Field(ge=0, le=1, description="Overall confidence in this decision.")
    reasoning_summary: str | None = Field(
        default=None,
        description="One short sentence. Do not give legal advice.",
    )
