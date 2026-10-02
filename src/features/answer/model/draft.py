"""Build the proposal from locked facts and already layered passages."""

from dataclasses import dataclass
from datetime import date

from src.features.answer.model.assessment import Assessment
from src.features.answer.model.decide import DecisionInput, SanctionDecision, decide
from src.features.answer.model.layers import LayeredBasis
from src.features.answer.schema.render import RenderInput, render


@dataclass(frozen=True)
class AnswerDraft:
    """Prose plus the columns stored on ``recommendations``."""

    prose: str
    decision: SanctionDecision


@dataclass(frozen=True)
class AnswerInput:
    """The recommend node's input."""

    family: str
    facts: dict[str, str]
    fact_lines: list[str]
    employee_name: str | None
    incident_date: date
    layered: LayeredBasis
    precedent_note: str
    retrieval: str = "hybrid"
    description: str = ""


def draft_answer(data: AnswerInput, assessment: Assessment | None = None) -> AnswerDraft:
    """Decide the level from a guarded assessment, then write the message HR will read."""
    decision = decide(
        DecisionInput(
            family=data.family,
            facts=data.facts,
            layered=data.layered,
            retrieval=data.retrieval,
            description=data.description,
            fact_lines=tuple(data.fact_lines),
        ),
        assessment,
    )
    report = assessment.report.strip() if assessment is not None else ""
    prose = report or render(
        RenderInput(
            employee_name=data.employee_name,
            incident_date=data.incident_date,
            fact_lines=data.fact_lines,
            decision=decision,
            layered=data.layered,
            precedent_note=data.precedent_note,
        )
    )
    return AnswerDraft(prose=prose, decision=decision)
