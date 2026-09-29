"""API shape of a layered answer."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

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


class AnswerView(BaseModel):
    """The proposal HR reads. Sanction is null when the grounds are not enough."""

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


SANCTION_LABELS = {
    "WARNING": "khiển trách (WARNING)",
    "REPRIMAND": "cảnh cáo (REPRIMAND)",
    "WAGE_POSTPONEMENT": "kéo dài thời hạn nâng lương (WAGE_POSTPONEMENT)",
    "DEMOTION": "cách chức (DEMOTION)",
    "DISMISSAL": "sa thải (DISMISSAL)",
    "TERMINATION": "chấm dứt hợp đồng (TERMINATION)",
}
