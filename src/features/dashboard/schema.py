"""Dashboard payloads. Counts never include a case the caller cannot open."""

from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    cases_by_status: dict[str, int] = Field(default_factory=dict)
    cases_by_family: dict[str, int] = Field(default_factory=dict)
    recommendation_rejection_rate: float | None = None
    legal_approval_rate: float | None = None
    legal_rejection_rate: float | None = None
    agent_failure_rate: float | None = None
    retrieval_empty_rate: float | None = None


class CasesResponse(BaseModel):
    cases_by_status: dict[str, int] = Field(default_factory=dict)
    cases_by_family: dict[str, int] = Field(default_factory=dict)


class ProcessingTimeResponse(BaseModel):
    open_to_analyzed_seconds: float | None = None
    analyzed_to_pending_legal_seconds: float | None = None
    pending_legal_to_approved_seconds: float | None = None
    approved_to_decided_seconds: float | None = None
    total_processing_seconds: float | None = None
    sample_size: int = 0


class SanctionsResponse(BaseModel):
    cases_by_sanction: dict[str, int] = Field(default_factory=dict)
