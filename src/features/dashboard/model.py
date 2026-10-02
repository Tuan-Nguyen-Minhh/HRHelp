"""Aggregate metrics for cases the caller is allowed to see."""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import case_visibility
from src.features.dashboard.schema import CasesResponse, ProcessingTimeResponse, SanctionsResponse, SummaryResponse
from src.models.agent_runs import AgentRun
from src.models.audit_logs import AuditLog
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.recommendations import Recommendation
from src.models.reviews import Review
from src.models.tool_calls import ToolCall
from src.models.users import User


async def summary(session: AsyncSession, actor: User) -> SummaryResponse:
    """Status, family, and rates. Another employee's case is not counted."""
    cases = await _cases(session, actor)
    by_status, by_family = _group_cases(cases)
    case_ids = [row.id for row in cases]
    rejection = await _recommendation_rejection_rate(session, case_ids)
    approved, rejected = await _legal_counts(session, case_ids)
    legal_total = approved + rejected
    return SummaryResponse(
        cases_by_status=by_status,
        cases_by_family=by_family,
        recommendation_rejection_rate=rejection,
        legal_approval_rate=None if legal_total == 0 else approved / legal_total,
        legal_rejection_rate=None if legal_total == 0 else rejected / legal_total,
        agent_failure_rate=await _agent_failure_rate(session, case_ids),
        retrieval_empty_rate=await _retrieval_empty_rate(session, case_ids),
    )


async def cases_breakdown(session: AsyncSession, actor: User) -> CasesResponse:
    by_status, by_family = _group_cases(await _cases(session, actor))
    return CasesResponse(cases_by_status=by_status, cases_by_family=by_family)


async def processing_time(session: AsyncSession, actor: User) -> ProcessingTimeResponse:
    """Average durations from audit rows, with case and decision timestamps as a fallback."""
    cases = await _cases(session, actor)
    if not cases:
        return ProcessingTimeResponse()
    case_ids = [row.id for row in cases]
    opened = {row.id: row.created_at for row in cases}
    analyzed = await _first_recommendation_at(session, case_ids)
    audits = list(
        (
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.case_id.in_(case_ids),
                    AuditLog.action.in_(
                        (
                            "RECOMMENDATION_CREATED",
                            "LEGAL_TICKET_SUBMITTED",
                            "LEGAL_APPROVED",
                            "DECISION_ISSUED",
                        )
                    ),
                )
            )
        ).all()
    )
    pending: dict = {}
    approved: dict = {}
    decided: dict = {}
    for row in audits:
        if row.case_id is None:
            continue
        if row.action == "RECOMMENDATION_CREATED":
            analyzed[row.case_id] = _earlier(analyzed.get(row.case_id), row.created_at)
        elif row.action == "LEGAL_TICKET_SUBMITTED":
            pending[row.case_id] = _earlier(pending.get(row.case_id), row.created_at)
        elif row.action == "LEGAL_APPROVED":
            approved[row.case_id] = _earlier(approved.get(row.case_id), row.created_at)
        elif row.action == "DECISION_ISSUED":
            decided[row.case_id] = _earlier(decided.get(row.case_id), row.created_at)
    decisions = list(
        (await session.scalars(select(DisciplinaryDecision).where(DisciplinaryDecision.case_id.in_(case_ids)))).all()
    )
    for row in decisions:
        decided[row.case_id] = decided.get(row.case_id) or row.issued_at
    return ProcessingTimeResponse(
        open_to_analyzed_seconds=_avg(_spans(opened, analyzed)),
        analyzed_to_pending_legal_seconds=_avg(_spans(analyzed, pending)),
        pending_legal_to_approved_seconds=_avg(_spans(pending, approved)),
        approved_to_decided_seconds=_avg(_spans(approved, decided)),
        total_processing_seconds=_avg(_spans(opened, decided)),
        sample_size=len(cases),
    )


async def sanctions(session: AsyncSession, actor: User) -> SanctionsResponse:
    cases = await _cases(session, actor)
    case_ids = [row.id for row in cases]
    counts: dict[str, int] = {}
    if not case_ids:
        return SanctionsResponse(cases_by_sanction=counts)
    rows = (
        await session.execute(
            select(DisciplinaryDecision.sanction_type, func.count())
            .where(DisciplinaryDecision.case_id.in_(case_ids))
            .group_by(DisciplinaryDecision.sanction_type)
        )
    ).all()
    counts = {str(kind): int(count) for kind, count in rows}
    return SanctionsResponse(cases_by_sanction=counts)


async def _cases(session: AsyncSession, actor: User) -> list[Case]:
    stmt = select(Case)
    visible = case_visibility(actor)
    if visible is not None:
        stmt = stmt.where(visible)
    return list((await session.scalars(stmt)).all())


def _group_cases(cases: list[Case]) -> tuple[dict[str, int], dict[str, int]]:
    by_status: dict[str, int] = defaultdict(int)
    by_family: dict[str, int] = defaultdict(int)
    for case in cases:
        by_status[case.status] += 1
        by_family[case.family or "UNSPECIFIED"] += 1
    return dict(by_status), dict(by_family)


async def _recommendation_rejection_rate(session: AsyncSession, case_ids: list) -> float | None:
    if not case_ids:
        return None
    rows = (
        await session.execute(
            select(Recommendation.status, func.count())
            .where(Recommendation.case_id.in_(case_ids), Recommendation.status.in_(("APPROVED", "REJECTED")))
            .group_by(Recommendation.status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    total = counts.get("APPROVED", 0) + counts.get("REJECTED", 0)
    if total == 0:
        return None
    return counts.get("REJECTED", 0) / total


async def _legal_counts(session: AsyncSession, case_ids: list) -> tuple[int, int]:
    if not case_ids:
        return 0, 0
    rows = (
        await session.execute(
            select(Review.decision, func.count()).where(Review.case_id.in_(case_ids)).group_by(Review.decision)
        )
    ).all()
    counts = {decision: int(count) for decision, count in rows}
    return counts.get("APPROVE", 0), counts.get("REJECT", 0)


async def _agent_failure_rate(session: AsyncSession, case_ids: list) -> float | None:
    if not case_ids:
        return None
    conversation_ids = list(
        (await session.scalars(select(Conversation.id).where(Conversation.case_id.in_(case_ids)))).all()
    )
    if not conversation_ids:
        return None
    rows = (
        await session.execute(
            select(AgentRun.status, func.count())
            .where(AgentRun.conversation_id.in_(conversation_ids))
            .group_by(AgentRun.status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    total = sum(counts.values())
    if total == 0:
        return None
    return counts.get("FAILED", 0) / total


async def _retrieval_empty_rate(session: AsyncSession, case_ids: list) -> float | None:
    if not case_ids:
        return None
    conversation_ids = list(
        (await session.scalars(select(Conversation.id).where(Conversation.case_id.in_(case_ids)))).all()
    )
    if not conversation_ids:
        return None
    run_ids = list(
        (await session.scalars(select(AgentRun.id).where(AgentRun.conversation_id.in_(conversation_ids)))).all()
    )
    if not run_ids:
        return None
    tools = list(
        (
            await session.scalars(
                select(ToolCall).where(ToolCall.agent_run_id.in_(run_ids), ToolCall.tool_name == "search_policy")
            )
        ).all()
    )
    if not tools:
        return None
    empty = 0
    for tool in tools:
        output = tool.output or {}
        count = output.get("count") if isinstance(output, dict) else None
        if count == 0:
            empty += 1
    return empty / len(tools)


async def _first_recommendation_at(session: AsyncSession, case_ids: list) -> dict:
    rows = (
        await session.execute(
            select(Recommendation.case_id, func.min(Recommendation.created_at))
            .where(Recommendation.case_id.in_(case_ids))
            .group_by(Recommendation.case_id)
        )
    ).all()
    return {case_id: moment for case_id, moment in rows}


def _earlier(current: datetime | None, candidate: datetime) -> datetime:
    if current is None or candidate < current:
        return candidate
    return current


def _spans(start: dict, end: dict) -> list[float]:
    values = []
    for key, began in start.items():
        finished = end.get(key)
        if began is None or finished is None:
            continue
        delta = (finished - began).total_seconds()
        if delta >= 0:
            values.append(delta)
    return values


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
