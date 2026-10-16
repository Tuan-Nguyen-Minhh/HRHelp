"""Contracts for the legal queue. The body cannot change a sanction or a fact."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.common.text import UppercaseText
from src.features.answer.schema import AnswerView
from src.features.assessment.schemas import AssessmentView


class ReviewRequest(BaseModel):
    """Human decision. Extra fields such as sanction_type are rejected."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVE", "REJECT"]
    comment: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def reject_needs_comment(self) -> "ReviewRequest":
        """A return to HR must say what to fix. Approval may omit the note."""
        if self.decision == "REJECT" and not (self.comment or "").strip():
            raise ValueError("Yêu cầu xử lý lại cần ghi việc HR phải làm.")
        return self


class ReviewView(BaseModel):
    review_id: UUID
    case_id: UUID
    decision: str
    comment: str | None
    case_status: str


class ReturnReason(BaseModel):
    reviewer_role: Literal["LEGAL", "MANAGER"]
    reviewer_name: str | None
    comment: str | None
    returned_at: datetime


class QueueItem(BaseModel):
    case_id: UUID
    case_code: UppercaseText
    employee_code: UppercaseText | None
    employee_name: UppercaseText | None
    incident_date: date | None
    status: str
    updated_at: datetime


class QueueResponse(BaseModel):
    reviews: list[QueueItem]


class ReviewPack(BaseModel):
    """What legal reads. It is the stored assessment, not a new agent run."""

    case_id: UUID
    case_code: UppercaseText
    status: str
    employee_code: UppercaseText | None
    employee_name: UppercaseText | None
    incident_date: date | None
    description: str | None
    answer: AnswerView
    assessment: AssessmentView | None = None
