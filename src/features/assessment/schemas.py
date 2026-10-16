"""Assessment form contract. Extra citation ids and sanction codes are rejected."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.common.minutes_profile import MinutesProfile
from src.common.text import UppercaseText

FormStatus = Literal["AI_DRAFT", "HR_EDITING", "READY_FOR_CONFIRM", "CONFIRMED", "SUPERSEDED"]
ReportStatus = Literal["DRAFT", "CONFIRMED", "SUPERSEDED"]
FactStatus = Literal["CONFIRMED", "MISSING", "UNCERTAIN", "HR_EDITED"]
FieldSource = Literal["AI", "HR", "CONFIRMED"]
ResultStatus = Literal[
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "NEED_LEGAL_REVIEW",
]


class CaseInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_code: UppercaseText
    incident_date: date | None = None
    violation_type: str | None = None
    description: str = ""
    case_status: str


class EmployeeInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_code: UppercaseText | None = None
    employee_name: UppercaseText | None = None
    department: str | None = None
    position: str | None = None
    contract_type: str | None = None
    employment_status: str | None = None


class IncidentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = ""
    timeline: str = ""
    employee_statement: str = ""
    hr_description: str = ""


class ConfirmedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_key: str
    label: str
    value: str | None = None
    status: FactStatus
    blocking: bool = False
    source: FieldSource = "AI"


class EvidenceCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    policy_type: str | None = None
    title: str
    citation_label: str
    quote: str
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    layer: str


class AssessmentSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = ""
    applied_basis: list[str] = Field(default_factory=list)
    matches: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class AssessmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ResultStatus
    summary: str


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str


class HandlingProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    alternatives: list[ProposedAction] = Field(default_factory=list)
    confidence: str = "LOW"
    requires_legal_review: bool = True
    rationale: str = ""
    manual_text: str | None = None


class MissingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_key: str
    reason: str
    blocking: bool


class RiskAndGaps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: str | None = None
    evidence_gaps: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    missing_information: list[MissingItem] = Field(default_factory=list)
    legal_review_required: bool = True


class NextStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    text: str


class Sections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_information: CaseInformation
    employee_information: EmployeeInformation
    incident_summary: IncidentSummary
    confirmed_facts: list[ConfirmedFact]
    evidence_reviewed: list[EvidenceCard]
    assessment: AssessmentSection
    assessment_result: AssessmentResult
    handling_proposal: HandlingProposal
    risk_and_gaps: RiskAndGaps
    next_steps: list[NextStep]
    citations: list[EvidenceCard]


class ValidationState(BaseModel):
    is_valid: bool
    blocking_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Permissions(BaseModel):
    can_edit: bool
    can_confirm: bool
    can_reanalyze: bool
    can_create_ticket: bool


class AssessmentMetadata(BaseModel):
    generated_at: datetime | None = None
    case_created_date: date | None = None
    minutes_profile: MinutesProfile = Field(default_factory=MinutesProfile)
    source: Literal["AI", "HR"]
    recommendation_id: UUID | None = None
    prompt_version: str = "assessment-form-v1"


class AssessmentPatch(BaseModel):
    """HR edits. Citation ids, scores, and sanction codes are not accepted."""

    model_config = ConfigDict(extra="forbid")

    case_information: CaseInformation | None = None
    employee_information: EmployeeInformation | None = None
    incident_summary: IncidentSummary | None = None
    confirmed_facts: list[ConfirmedFact] | None = None
    handling_rationale: str | None = Field(default=None, max_length=4000)


class AssessmentView(BaseModel):
    assessment_id: UUID
    case_id: UUID
    version: int
    status: ReportStatus
    form_status: FormStatus
    sections: Sections
    validation: ValidationState
    permissions: Permissions
    metadata: AssessmentMetadata
    sources: dict[str, FieldSource] = Field(default_factory=dict)
