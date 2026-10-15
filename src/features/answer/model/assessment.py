"""Structured assessment the synthesis model must return.

Python checks that every cited quote sits inside a retrieved passage.
The model does not become a source of legal rules.
"""

from typing import Literal

from pydantic import BaseModel, Field

DecisionStatus = Literal[
    "SUPPORTED",
    "NOT_SUPPORTED",
    "NEED_MORE_FACTS",
    "MULTIPLE_SUPPORTED",
    "CONFLICTED",
    "NEED_LEGAL_REVIEW",
]
Relevance = Literal["RELEVANT", "PARTIALLY_RELEVANT", "IRRELEVANT"]
ConditionResult = Literal["SATISFIED", "NOT_SATISFIED", "UNKNOWN", "CONFLICTED"]
DocumentType = Literal["LAW", "DECREE", "INTERNAL_RULE"]
ProcedureStatus = Literal["REQUIRED", "OPTIONAL", "UNKNOWN"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class EvidenceRef(BaseModel):
    chunk_id: str
    quote: str
    source: Literal["CONTENT", "HEADING"] = "CONTENT"


class CaseSummary(BaseModel):
    violation: str = ""
    facts: dict[str, str] = Field(default_factory=dict)
    missing_facts: list[str] = Field(default_factory=list)


class PassageNote(BaseModel):
    chunk_id: str
    relevance: Relevance
    note: str = ""


class EvidenceSummary(BaseModel):
    law: list[PassageNote] = Field(default_factory=list)
    decree: list[PassageNote] = Field(default_factory=list)
    internal_rule: list[PassageNote] = Field(default_factory=list)
    precedent: list[PassageNote] = Field(default_factory=list)
    administrative_penalty: list[PassageNote] = Field(default_factory=list)


class RuleCondition(BaseModel):
    fact: str
    required: str
    result: ConditionResult
    fact_value: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)
    scope: Literal["SUBSTANTIVE", "ISSUANCE"] = "SUBSTANTIVE"
    alternative_group: str = Field(
        default="", description="Nonempty groups are alternative AND branches; empty = mandatory."
    )


class ApplicableRule(BaseModel):
    rule_id: str
    document_type: DocumentType
    description: str
    conditions: list[RuleCondition] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    supports_sanction: str | None = None
    purpose: Literal["SANCTION", "CONTEXT", "PROCEDURE"] = "SANCTION"
    selected: bool = True


class SanctionItem(BaseModel):
    sanction: str
    status: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class SanctionAssessment(BaseModel):
    status: DecisionStatus
    recommended_sanction: str | None = None
    supported_sanctions: list[SanctionItem] = Field(default_factory=list)
    excluded_sanctions: list[SanctionItem] = Field(default_factory=list)
    reason: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ProcedureStepView(BaseModel):
    step: str
    status: ProcedureStatus
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ProcedureAssessment(BaseModel):
    status: Literal["SUPPORTED", "PARTIAL", "UNKNOWN"] = "UNKNOWN"
    steps: list[ProcedureStepView] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    level: RiskLevel
    reasons: list[str] = Field(default_factory=list)


class EvidenceGap(BaseModel):
    fact: str
    reason: str
    question_for_user: str


class Conflict(BaseModel):
    topic: str
    sources: list[str] = Field(default_factory=list)
    description: str


class SeverityAssessment(BaseModel):
    """Descriptive seriousness, never a lookup table for a sanction."""

    score: int | None = Field(default=None, ge=1, le=5)
    reason: str = "Chưa đủ dữ kiện để đánh giá mức độ nghiêm trọng."
    fact_keys: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class IssuanceCheck(BaseModel):
    category: Literal["TIME_LIMIT", "PROTECTION", "PROCEDURE", "AUTHORITY", "SOURCE_VALIDITY"]
    requirement: str
    result: ConditionResult = "UNKNOWN"
    effect: Literal["PROCEDURE", "TEMPORARY_BLOCK", "LEGAL_BLOCK"] = "PROCEDURE"
    fact_values: dict[str, str] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    next_action: str = ""


class RubricReasoning(BaseModel):
    severity: SeverityAssessment = Field(default_factory=SeverityAssessment)
    issuance_checks: list[IssuanceCheck] = Field(default_factory=list)


class SupportDimension(BaseModel):
    key: str
    score: int = Field(ge=0, le=100)
    explanation: str


class SourceSupport(BaseModel):
    chunk_id: str
    policy_version_id: str
    document_role: str
    content_sha256: str
    heading_sha256: str
    citation_integrity_score: int = Field(ge=0, le=100)
    retrieval_status: str
    note: str = "Điểm khớp trích dẫn, chưa phải độ đúng pháp lý của văn bản."


class ConfidenceAssessment(BaseModel):
    """Observable evidence support, not calibrated correctness probability."""

    rubric_version: str = "hr-reasoning-v1"
    score: int = Field(default=0, ge=0, le=100)
    label: Literal["LOW", "MEDIUM", "HIGH", "UNASSESSED"] = "UNASSESSED"
    score_kind: Literal["EVIDENCE_SUPPORT_INDEX"] = "EVIDENCE_SUPPORT_INDEX"
    calibrated: bool = False
    dimensions: list[SupportDimension] = Field(default_factory=list)
    sources: list[SourceSupport] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class IssuanceAssessment(BaseModel):
    status: Literal[
        "NEEDS_VERIFICATION", "NEEDS_PROCEDURE", "TEMPORARILY_BLOCKED", "LEGALLY_BLOCKED", "READY_FOR_HUMAN_REVIEW"
    ] = "NEEDS_VERIFICATION"
    checks: list[IssuanceCheck] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    human_approval_required: bool = True


class DownstreamHandoff(BaseModel):
    """Machine-readable part of the case report. It never creates a legal ticket."""

    can_recommend: bool = False
    can_finalize: bool = False
    needs_clarification: bool = False
    needs_legal_review: bool = False
    assessment_status: str = ""
    recommended_sanction: str | None = None
    risk_level: str = ""
    legal_basis_found: bool = False
    internal_rule_found: bool = False
    procedure_status: str = "UNKNOWN"
    needs_more_facts: bool = False
    missing_facts: list[str] = Field(default_factory=list)
    hr_decision_required: bool = True
    can_create_legal_ticket: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    next_allowed_actions: list[str] = Field(
        default_factory=lambda: [
            "CONTINUE",
            "REQUEST_MORE_INFORMATION",
            "SEND_TO_LEGAL",
            "REJECT_ASSESSMENT",
        ]
    )


class Assessment(BaseModel):
    """One traceable reading of the retrieved passages. Downstream agents consume this object."""

    case_summary: CaseSummary
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    applicable_rules: list[ApplicableRule] = Field(default_factory=list)
    sanction_assessment: SanctionAssessment
    procedure_assessment: ProcedureAssessment = Field(default_factory=ProcedureAssessment)
    risk_assessment: RiskAssessment
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    report: str = Field(
        default="",
        description=(
            "PART A. Biên bản đánh giá vụ việc bằng tiếng Việt, bắt đầu bằng "
            "'BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC' và đủ mục I đến XI. Đây không phải quyết định kỷ luật."
        ),
    )
    downstream_handoff: DownstreamHandoff = Field(default_factory=DownstreamHandoff)
    operational_status: Literal["OK", "LLM_FAILED", "RERANK_FAILED"] = "OK"
    rubric_reasoning: RubricReasoning = Field(default_factory=RubricReasoning)
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment)
    issuance: IssuanceAssessment = Field(default_factory=IssuanceAssessment)


class SynthesisAssessment(BaseModel):
    """Only the reasoning result is generated. Python renders report and handoff."""

    case_summary: CaseSummary
    applicable_rules: list[ApplicableRule] = Field(default_factory=list)
    sanction_assessment: SanctionAssessment
    procedure_assessment: ProcedureAssessment = Field(default_factory=ProcedureAssessment)
    risk_assessment: RiskAssessment
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    rubric_reasoning: RubricReasoning = Field(default_factory=RubricReasoning)
