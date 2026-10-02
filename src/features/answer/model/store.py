"""Persist the recommendation, its citations, and the linked violation."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.models.case_drafts import CaseDraft
from src.models.case_violations import CaseViolation
from src.models.recommendation_citations import RecommendationCitation
from src.models.recommendations import Recommendation
from src.models.violation_types import ViolationType


@dataclass(frozen=True)
class CitationDraft:
    """One quote about to be stored."""

    chunk_id: UUID
    quote: str
    article: str | None
    clause: str | None
    point: str | None
    score: float


@dataclass(frozen=True)
class CitationRow:
    """A stored citation joined back to its policy."""

    citation_id: UUID
    chunk_id: UUID | None
    quote: str
    article: str | None
    clause: str | None
    point: str | None
    score: float | None
    policy_type: str | None
    policy_code: str | None
    policy_name: str | None


async def supersede_drafts(session: AsyncSession, case_id: UUID) -> None:
    """Mark current drafts superseded. Approved rows are left untouched."""
    stmt = select(Recommendation).where(Recommendation.case_id == case_id, Recommendation.status == "DRAFT")
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        row.status = "SUPERSEDED"


_DRAFT_ORDER = {"MINUTES": 0, "EXPLANATION_REQUEST": 1, "DECISION": 2, "TICKET": 3}


async def list_case_drafts(session: AsyncSession, recommendation_id: UUID) -> list[CaseDraft]:
    """Return drafts written for this recommendation, in ticket order."""
    stmt = select(CaseDraft).where(CaseDraft.recommendation_id == recommendation_id)
    rows = list((await session.execute(stmt)).scalars().all())
    rows.sort(key=lambda row: _DRAFT_ORDER.get(row.draft_type, 9))
    return rows


async def latest_recommendation(session: AsyncSession, case_id: UUID) -> Recommendation | None:
    """Return the newest recommendation that has not been superseded."""
    stmt = (
        select(Recommendation)
        .where(Recommendation.case_id == case_id, Recommendation.status != "SUPERSEDED")
        .order_by(Recommendation.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def insert_recommendation(session: AsyncSession, row: Recommendation) -> Recommendation:
    """Insert a DRAFT recommendation. The caller fills the columns."""
    session.add(row)
    await session.flush()
    return row


async def insert_citations(session: AsyncSession, recommendation_id: UUID, items: list[CitationDraft]) -> list:
    """Store quotes in the same order they will be shown."""
    rows = []
    for item in items:
        row = RecommendationCitation(
            id=uuid4(),
            recommendation_id=recommendation_id,
            chunk_id=item.chunk_id,
            quote=item.quote,
            article=item.article,
            clause=item.clause,
            point=item.point,
            score=item.score,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def list_citation_rows(session: AsyncSession, recommendation_id: UUID) -> list[CitationRow]:
    """Read citations with the policy that owns each chunk."""
    from src.models.document_chunks import DocumentChunk
    from src.models.documents import Document
    from src.models.policies import Policy
    from src.models.policy_versions import PolicyVersion

    stmt = (
        select(
            RecommendationCitation.id,
            RecommendationCitation.chunk_id,
            RecommendationCitation.quote,
            RecommendationCitation.article,
            RecommendationCitation.clause,
            RecommendationCitation.point,
            RecommendationCitation.score,
            Policy.policy_type,
            Policy.code,
            Policy.name,
        )
        .join(DocumentChunk, DocumentChunk.id == RecommendationCitation.chunk_id, isouter=True)
        .join(Document, Document.id == DocumentChunk.document_id, isouter=True)
        .join(PolicyVersion, PolicyVersion.id == Document.policy_version_id, isouter=True)
        .join(Policy, Policy.id == PolicyVersion.policy_id, isouter=True)
        .where(RecommendationCitation.recommendation_id == recommendation_id)
        .order_by(RecommendationCitation.score.desc())
    )
    return [_citation_row(row) for row in (await session.execute(stmt)).all()]


async def ensure_violation(session: AsyncSession, case_id: UUID, code: str, evidence: str, severity: str) -> bool:
    """Link the case to a seeded violation type. Missing catalog rows are skipped."""
    kind = await _violation_type(session, code)
    if kind is None:
        return False
    current = await _case_violation(session, case_id, kind.id)
    if current is None:
        session.add(
            CaseViolation(
                id=uuid4(),
                case_id=case_id,
                violation_type_id=kind.id,
                evidence=evidence,
                severity=severity,
            )
        )
    else:
        current.evidence = evidence
        current.severity = severity
    await session.flush()
    return True


async def _violation_type(session: AsyncSession, code: str) -> ViolationType | None:
    stmt = select(ViolationType).where(ViolationType.code == code, ViolationType.is_active.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()


async def _case_violation(session: AsyncSession, case_id: UUID, type_id: UUID) -> CaseViolation | None:
    stmt = select(CaseViolation).where(CaseViolation.case_id == case_id, CaseViolation.violation_type_id == type_id)
    return (await session.execute(stmt)).scalars().first()


def _citation_row(row: object) -> CitationRow:
    return CitationRow(
        citation_id=row.id,
        chunk_id=row.chunk_id,
        quote=row.quote,
        article=row.article,
        clause=row.clause,
        point=row.point,
        score=row.score,
        policy_type=row.policy_type,
        policy_code=row.code,
        policy_name=row.name,
    )
