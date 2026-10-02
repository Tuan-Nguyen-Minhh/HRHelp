"""API shape of a layered answer."""

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.features.answer.model.layers import BasisLayer


class ProcessStep(BaseModel):
    """One procedural step HR still has to complete or has already completed."""

    model_config = ConfigDict(frozen=True)

    code: str
    label: str
    done: bool


class CitationView(BaseModel):
    """One quote, already placed in its layer."""

    citation_id: UUID
    chunk_id: UUID | None
    layer: BasisLayer
    policy_type: str | None
    policy_code: str | None
    policy_name: str | None
    quote: str
    article: str | None
    clause: str | None
    point: str | None
    score: float | None


class LayerEffect(BaseModel):
    """What one retrieved layer is allowed to do to the company sanction."""

    model_config = ConfigDict(frozen=True)

    layer: str
    effect: str
    note: str


class AppliedStandard(BaseModel):
    """The one sanction and process feature 6 returns after the sources are reconciled."""

    model_config = ConfigDict(frozen=True)

    sanction_type: str | None
    process_steps: list[ProcessStep]
    risk_level: str | None
    aligned: bool
    rule: str
    layers: list[LayerEffect]


class DraftView(BaseModel):
    """One stored case draft. Feature 7 writes these; the screen only reads them."""

    model_config = ConfigDict(frozen=True)

    draft_id: UUID
    draft_type: str
    title: str
    content: str
    status: str


class TicketRequest(BaseModel):
    """Whether feature 7 sent the legal ticket, and where feature 8 would read it."""

    model_config = ConfigDict(frozen=True)

    disposition: str
    hold_code: str | None = None
    reason: str
    queue: str


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LegalOfficer(BaseModel):
    """One active pháp chế account HR can address by email."""

    email: str
    full_name: str | None = None


class LegalOfficerList(BaseModel):
    users: list[LegalOfficer]


class SendTicketRequest(BaseModel):
    """HR confirms the preview and names the legal recipient by email."""

    model_config = ConfigDict(str_strip_whitespace=True)

    legal_code: str = Field(min_length=3, max_length=255)

    @field_validator("legal_code")
    @classmethod
    def fold_email(cls, value: str) -> str:
        email = value.strip().casefold()
        if _EMAIL.fullmatch(email) is None:
            raise ValueError("Email pháp chế không hợp lệ.")
        return email


class AnswerView(BaseModel):
    """The proposal HR reads. Sanction is null when the grounds are not enough.

    ``drafts`` are the current recommendation's case drafts. ``ticket`` says
    whether those drafts were submitted to the legal queue. Neither field
    chooses a new sanction.
    """

    recommendation_id: UUID
    case_id: UUID
    case_status: str
    agent_run_id: UUID | None
    rationale: str | None
    sanction_type: str | None
    process_steps: list[ProcessStep]
    risk_level: str | None
    missing_internal_rule: bool
    message: str
    legal_basis: list[CitationView]
    internal_rule: list[CitationView]
    precedent: list[CitationView]
    inspection_risk: list[CitationView]
    standard: AppliedStandard
    drafts: list[DraftView] = Field(default_factory=list)
    ticket: TicketRequest | None = None


SANCTION_LABELS = {
    "WARNING": "khiển trách (WARNING)",
    "REPRIMAND": "cảnh cáo (REPRIMAND)",
    "WAGE_POSTPONEMENT": "kéo dài thời hạn nâng lương (WAGE_POSTPONEMENT)",
    "DEMOTION": "cách chức (DEMOTION)",
    "DISMISSAL": "sa thải (DISMISSAL)",
    "TERMINATION": "chấm dứt hợp đồng (TERMINATION)",
}
