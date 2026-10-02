"""Message the intake agent hands to the sanction agent.

Chat-clarify and cite fill one ``CaseHandoff``. The sanction agent
(sanction type, process steps, risk) reads that object and does not read
chat state, extracted-but-unconfirmed facts, or the database session.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CitedPassage(BaseModel):
    """One chunk cite kept. Order in ``CaseHandoff.passages`` is rank order."""

    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    policy_version_id: UUID
    content: str
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    score: float
    policy_type: str | None = None
    policy_code: str
    policy_name: str
    origin: str = "hybrid"


class CaseHandoff(BaseModel):
    """Standard payload produced after facts are confirmed and policies are cited.

    ``family`` is ``UNAUTHORIZED_ABSENCE``, ``LATE``, or ``GENERAL``.
    ``facts`` contains only confirmed values. ``passages`` are chunks whose
    policy version was in force on ``incident_date``. ``missing_internal_rule``
    is true when none of those chunks has ``policy_type`` ``INTERNAL_RULE``.
    ``retrieval`` is ``hybrid`` after rank fusion, ``page_index`` when only the
    article outline matched, or ``empty`` when no in-force chunk matched.
    """

    model_config = ConfigDict(frozen=True)

    case_id: UUID | None = None
    employee_code: str | None = None
    incident_date: date
    employee_name: str | None = None
    description: str = ""
    family: str
    facts: dict[str, str]
    fact_lines: list[str] = Field(default_factory=list)
    passages: list[CitedPassage] = Field(default_factory=list)
    missing_internal_rule: bool
    agent_run_id: UUID
    query: str = ""
    retrieval: str = "hybrid"
