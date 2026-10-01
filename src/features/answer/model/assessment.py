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
ConditionResult = Literal["SATISFIED", "NOT_SATISFIED", "UNKNOWN"]
DocumentType = Literal["LAW", "DECREE", "INTERNAL_RULE"]
ProcedureStatus = Literal["REQUIRED", "OPTIONAL", "UNKNOWN"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class EvidenceRef(BaseModel):
    chunk_id: str
    quote: str


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


class ApplicableRule(BaseModel):
    rule_id: str
    document_type: DocumentType
    description: str
    conditions: list[RuleCondition] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


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


class DownstreamHandoff(BaseModel):
    can_recommend: bool = False
    can_finalize: bool = False
    needs_clarification: bool = False
    needs_legal_review: bool = False


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
    downstream_handoff: DownstreamHandoff = Field(default_factory=DownstreamHandoff)
