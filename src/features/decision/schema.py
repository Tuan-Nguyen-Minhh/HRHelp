"""Decision contracts. The client does not choose the sanction."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.common.text import UppercaseText


class ManagerQueueItem(BaseModel):
    case_id: UUID
    case_code: UppercaseText
    employee_code: UppercaseText | None
    employee_name: UppercaseText | None
    incident_date: date | None
    status: str
    updated_at: datetime


class ManagerQueueResponse(BaseModel):
    cases: list[ManagerQueueItem]


class DecisionPreview(BaseModel):
    case_id: UUID
    case_status: str
    draft_id: UUID
    recommendation_id: UUID
    sanction_type: str
    decision_draft: str
    summary_hint: str | None


class IssueDecisionRequest(BaseModel):
    """Identity of the decision. ``sanction_type`` is derived on the server."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision_code: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=8000)
    legal_basis: str | None = Field(default=None, max_length=8000)


class DecisionView(BaseModel):
    decision_id: UUID
    case_id: UUID
    decision_code: str
    sanction_type: str
    summary: str
    legal_basis: str | None
    issued_by: UUID
    issued_at: datetime
    case_status: str
    is_precedent: bool


class PrecedentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    precedent_summary: str = Field(min_length=1, max_length=4000)


class CloseResponse(BaseModel):
    case_id: UUID
    status: str


class RejectDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    comment: str = Field(min_length=1, max_length=4000)
