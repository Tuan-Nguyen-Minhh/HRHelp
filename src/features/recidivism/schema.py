"""Recidivism report. The fact stays unconfirmed until HR accepts it."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PriorCase(BaseModel):
    case_id: UUID
    case_code: str
    status: str


class PriorDecision(BaseModel):
    decision_code: str
    sanction_type: str
    issued_at: datetime


class RecidivismView(BaseModel):
    case_id: UUID
    prior_sanction_count: int
    prior_cases: list[PriorCase] = Field(default_factory=list)
    prior_decisions: list[PriorDecision] = Field(default_factory=list)
    possible_recurrence: bool
    confirmed: bool
