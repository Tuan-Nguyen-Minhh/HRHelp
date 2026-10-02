"""Message feature 6 hands to the dispatch sub-agent.

The recommend graph does not write this object. ``publish`` stores the draft
first, then the caller closes one ``ProposalHandoff`` from that row and the
``CaseHandoff`` feature 6 already consumed. Dispatch reads only this message.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.agents.handoff import CaseHandoff
from src.features.answer.schema import AnswerView, AppliedStandard, CitationView, ProcessStep


class ProposalHandoff(BaseModel):
    """Frozen proposal. ``sanction_type`` is empty when feature 6 did not lock a level."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: UUID
    case_id: UUID
    agent_run_id: UUID
    incident_date: date
    employee_name: str | None = None
    employee_code: str | None = None
    family: str
    facts: dict[str, str]
    fact_lines: list[str] = Field(default_factory=list)
    rationale: str = ""
    sanction_type: str | None = None
    process_steps: list[ProcessStep] = Field(default_factory=list)
    risk_level: str | None = None
    missing_internal_rule: bool
    message: str
    legal_basis: list[CitationView] = Field(default_factory=list)
    internal_rule: list[CitationView] = Field(default_factory=list)
    precedent: list[CitationView] = Field(default_factory=list)
    inspection_risk: list[CitationView] = Field(default_factory=list)
    standard: AppliedStandard | None = None
    legal_code: str | None = None


def close_proposal(
    message: CaseHandoff,
    answer: AnswerView,
    *,
    employee_code: str | None = None,
    legal_code: str | None = None,
) -> ProposalHandoff:
    """Pack the stored draft and the identity fields feature 6 already held."""
    return ProposalHandoff(
        recommendation_id=answer.recommendation_id,
        case_id=message.case_id or answer.case_id,
        agent_run_id=answer.agent_run_id or message.agent_run_id,
        incident_date=message.incident_date,
        employee_name=message.employee_name,
        employee_code=employee_code,
        family=message.family,
        facts=dict(message.facts),
        fact_lines=list(message.fact_lines),
        rationale=answer.rationale or "",
        sanction_type=answer.sanction_type,
        process_steps=list(answer.process_steps),
        risk_level=answer.risk_level,
        missing_internal_rule=answer.missing_internal_rule,
        message=answer.message,
        legal_basis=list(answer.legal_basis),
        internal_rule=list(answer.internal_rule),
        precedent=list(answer.precedent),
        inspection_risk=list(answer.inspection_risk),
        standard=answer.standard,
        legal_code=legal_code,
    )
