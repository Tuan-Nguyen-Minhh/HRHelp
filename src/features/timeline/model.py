"""Build a timeline from messages, runs, tools, recommendations, drafts, reviews, decisions, and audits."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case
from src.features.clarify.model.store import list_messages
from src.features.opencase.model.cases import active_conversation
from src.features.timeline.schema import TimelineEvent, TimelineResponse
from src.models.agent_runs import AgentRun
from src.models.audit_logs import AuditLog
from src.models.case_drafts import CaseDraft
from src.models.conversations import Conversation
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.recommendations import Recommendation
from src.models.reviews import Review
from src.models.tool_calls import ToolCall
from src.models.users import User

_MESSAGE_KIND = {
    "USER": "USER_MESSAGE",
    "ASSISTANT": "ASSISTANT_MESSAGE",
    "SYSTEM": "SYSTEM_MESSAGE",
    "TOOL": "TOOL_MESSAGE",
}


async def case_timeline(session: AsyncSession, actor: User, case_id: UUID) -> TimelineResponse:
    """Return stored events in time order. Nothing here calls an agent."""
    case = await require_case(session, case_id, actor)
    events: list[TimelineEvent] = []
    conversations = list((await session.scalars(select(Conversation).where(Conversation.case_id == case.id))).all())
    conversation_ids = [row.id for row in conversations]
    active = await active_conversation(session, case.id)
    if active is not None and active.id not in conversation_ids:
        conversation_ids.append(active.id)
    for conversation_id in conversation_ids:
        for message in await list_messages(session, conversation_id):
            events.append(
                TimelineEvent(
                    at=message.created_at,
                    kind=_MESSAGE_KIND.get(message.role, message.role),
                    label=message.content[:180],
                    entity_type="messages",
                    entity_id=message.id,
                )
            )
        runs = list(
            (await session.scalars(select(AgentRun).where(AgentRun.conversation_id == conversation_id))).all()
        )
        for run in runs:
            events.append(
                TimelineEvent(
                    at=run.started_at,
                    kind="AGENT_RUN",
                    label=f"{run.agent_name or run.model or 'agent'} {run.status}",
                    entity_type="agent_runs",
                    entity_id=run.id,
                )
            )
            tools = list((await session.scalars(select(ToolCall).where(ToolCall.agent_run_id == run.id))).all())
            for tool in tools:
                events.append(
                    TimelineEvent(
                        at=tool.started_at,
                        kind="TOOL_CALL",
                        label=f"{tool.tool_name} {tool.status}",
                        entity_type="tool_calls",
                        entity_id=tool.id,
                    )
                )
    recommendations = list(
        (await session.scalars(select(Recommendation).where(Recommendation.case_id == case.id))).all()
    )
    for row in recommendations:
        events.append(
            TimelineEvent(
                at=row.created_at,
                kind="ASSESSMENT_CREATED",
                label=f"Đề xuất {row.status}",
                entity_type="recommendations",
                entity_id=row.id,
            )
        )
    drafts = list((await session.scalars(select(CaseDraft).where(CaseDraft.case_id == case.id))).all())
    for row in drafts:
        events.append(
            TimelineEvent(
                at=row.created_at,
                kind="DRAFT_STORED",
                label=f"{row.draft_type} {row.status}",
                entity_type="case_drafts",
                entity_id=row.id,
            )
        )
    reviews = list((await session.scalars(select(Review).where(Review.case_id == case.id))).all())
    for row in reviews:
        events.append(
            TimelineEvent(
                at=row.decided_at,
                kind="LEGAL_APPROVED" if row.decision == "APPROVE" else "LEGAL_REJECTED",
                label=row.comment or ("Pháp chế đã duyệt" if row.decision == "APPROVE" else "Pháp chế yêu cầu xử lý lại"),
                entity_type="reviews",
                entity_id=row.id,
            )
        )
    decision = await session.scalar(select(DisciplinaryDecision).where(DisciplinaryDecision.case_id == case.id))
    if decision is not None:
        events.append(
            TimelineEvent(
                at=decision.issued_at,
                kind="DECISION_ISSUED",
                label=decision.decision_code,
                entity_type="disciplinary_decisions",
                entity_id=decision.id,
            )
        )
    audits = list((await session.scalars(select(AuditLog).where(AuditLog.case_id == case.id))).all())
    for row in audits:
        events.append(
            TimelineEvent(
                at=row.created_at,
                kind=row.action,
                label=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
            )
        )
    events.sort(key=lambda item: item.at or datetime.min)
    return TimelineResponse(case_id=case.id, events=events)
