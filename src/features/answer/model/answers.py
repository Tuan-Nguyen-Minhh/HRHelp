"""Publish a layered answer and read the latest one back."""

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.common.text import clip_quote
from src.features.answer.model.draft import AnswerDraft
from src.features.answer.model.store import (
    CitationDraft,
    ensure_violation,
    insert_citations,
    insert_recommendation,
    latest_recommendation,
    list_citation_rows,
    supersede_drafts,
)
from src.features.answer.schema import AnswerView
from src.features.answer.schema.present import to_answer_view, view_from_passage, view_from_row
from src.features.cite.model.passage import Passage
from src.models.cases import Case
from src.models.recommendations import Recommendation

logger = logging.getLogger(__name__)


@dataclass
class PublishWork:
    """A locked case ready to be matched against the corpus."""

    case: Case
    family: str
    facts: dict[str, str]
    fact_lines: list[str]
    run_id: UUID
    text: str


async def publish(session: AsyncSession, work: PublishWork) -> AnswerView:
    """Supersede the previous draft, search, and store the new proposal.

    The caller commits. A failure rolls the new rows back with the fact update.
    """
    if work.case.incident_date is None:
        raise AppError(422, "Hồ sơ chưa có ngày xảy ra việc nên chưa đối chiếu được văn bản.")
    await supersede_drafts(session, work.case.id)
    draft, hits = await _draft(session, work)
    await _link_violation(session, work, draft.decision.risk_level)
    recommendation, views = await _store(session, work, draft, hits)
    work.case.status = "ANALYZED"
    return to_answer_view(recommendation, views, work.case.status)


async def load(session: AsyncSession, case: Case) -> AnswerView | None:
    """Return the current answer, or None when the case does not have one yet."""
    recommendation = await latest_recommendation(session, case.id)
    if recommendation is None:
        return None
    rows = await list_citation_rows(session, recommendation.id)
    return to_answer_view(recommendation, [view_from_row(row) for row in rows], case.status)


async def withdraw(session: AsyncSession, case_id: UUID) -> None:
    """Drop the active draft because a fact changed. The caller commits."""
    await supersede_drafts(session, case_id)


async def _draft(session: AsyncSession, work: PublishWork) -> tuple[AnswerDraft, list[Passage]]:
    state = await _run_graph(session, work)
    return state["draft"], list(state.get("hits") or [])


async def _run_graph(session: AsyncSession, work: PublishWork) -> dict:
    """Feature 6 fills this in. The case agent stops at ``CaseHandoff`` and does not draft."""
    del session, work
    raise AppError(501, "Agent đề xuất chế tài chưa gắn. Case agent chỉ trả message CaseHandoff.")


async def _link_violation(session: AsyncSession, work: PublishWork, severity: str) -> None:
    evidence = "; ".join(f"{key}={value}" for key, value in sorted(work.facts.items()))[:2000]
    linked = await ensure_violation(session, work.case.id, work.family, evidence, severity)
    if not linked:
        logger.info("violation type %s is not seeded", work.family)


async def _store(session: AsyncSession, work: PublishWork, draft: AnswerDraft, hits: list[Passage]) -> tuple:
    recommendation = await insert_recommendation(session, _recommendation(work, draft))
    rows = await insert_citations(session, recommendation.id, [_citation(passage) for passage in hits])
    views = [view_from_passage(row.id, passage) for row, passage in zip(rows, hits, strict=True)]
    return recommendation, views


def _recommendation(work: PublishWork, draft: AnswerDraft) -> Recommendation:
    steps = [step.model_dump() for step in draft.decision.process_steps]
    return Recommendation(
        id=uuid4(),
        case_id=work.case.id,
        agent_run_id=work.run_id,
        recommendation=draft.prose,
        rationale=draft.decision.rationale,
        sanction_type=draft.decision.sanction_type,
        process_steps=steps,
        risk_level=draft.decision.risk_level,
        status="DRAFT",
    )


def _citation(passage: Passage) -> CitationDraft:
    return CitationDraft(
        chunk_id=passage.chunk_id,
        quote=clip_quote(passage.content),
        article=passage.article,
        clause=passage.clause,
        point=passage.point,
        score=passage.score,
    )
