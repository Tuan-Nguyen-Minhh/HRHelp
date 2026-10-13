"""Orchestrate the downstream case agents after citation.

The case graph stops at ``CaseHandoff``. This module is the explicit parent
workflow for the remaining sub-agents:

    CaseHandoff -> recommendation assessment -> ProposalHandoff -> dispatch gate

The recommendation graph may use an LLM to synthesize evidence. The dispatch
graph is a deterministic gate that either holds the draft or prepares a ticket
preview. Human submission to legal remains a separate API call.
"""

import logging
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.handoff import CaseHandoff
from src.agents.runs import finish_run, start_run
from src.common.audit import write_audit
from src.common.clock import utc_now
from src.common.notify import notify
from src.features.answer.model.answers import PublishWork, attach_packet, publish
from src.features.answer.model.dispatch import DispatchResult, build_dispatch_agent, ready_to_dispatch
from src.features.answer.model.proposal import ProposalHandoff, close_proposal
from src.features.answer.model.send import ask_to_send, with_preview
from src.features.answer.schema import AnswerView
from src.features.clarify.model.store import NewMessage, add_message
from src.models.agent_runs import AgentRun
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.recommendations import Recommendation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownstreamAgentResult:
    """What the caller returns to HR after recommendation and dispatch."""

    answer: AnswerView
    agent_run_id: UUID
    assistant_text: str


async def run_downstream_agents(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    handoff: CaseHandoff,
    source_message_id: UUID,
) -> DownstreamAgentResult:
    """Run recommendation, then dispatch, from one immutable ``CaseHandoff``."""
    started = time.perf_counter()
    logger.info(
        "agent_stage start stage=downstream case_id=%s conversation_id=%s source_message_id=%s passages=%s retrieval=%s",
        case.id,
        conversation.id,
        source_message_id,
        len(handoff.passages),
        handoff.retrieval,
    )
    assessed = await run_recommendation_agent(session, case, conversation, handoff, source_message_id)
    dispatched = await run_dispatch_gate(session, case, conversation, handoff, assessed.answer, assessed.message_id)
    logger.info(
        "agent_stage end stage=downstream case_id=%s latency_ms=%s dispatched=%s",
        case.id,
        int((time.perf_counter() - started) * 1000),
        dispatched is not None,
    )
    if dispatched is not None:
        return dispatched
    return DownstreamAgentResult(assessed.answer, assessed.run_id, assessed.answer.message)


@dataclass(frozen=True)
class RecommendationStage:
    """Stored recommendation plus the assistant message that carries it."""

    answer: AnswerView
    run_id: UUID
    message_id: UUID


async def run_recommendation_agent(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    handoff: CaseHandoff,
    source_message_id: UUID,
) -> RecommendationStage:
    """Feature 6: read only ``CaseHandoff`` and store one draft assessment."""
    started = time.perf_counter()
    logger.info(
        "agent_stage start stage=recommendation case_id=%s conversation_id=%s passages=%s retrieval=%s",
        case.id,
        conversation.id,
        len(handoff.passages),
        handoff.retrieval,
    )
    run = await start_run(session, conversation.id, source_message_id, "hr-help-recommendation")
    answer = await publish(session, PublishWork(case=case, handoff=handoff, run_id=run.id))
    message = await add_message(
        session,
        NewMessage(conversation.id, "ASSISTANT", answer.message, {"kind": "recommendation"}),
    )
    finish_run(run, message.id)
    logger.info(
        "agent_stage end stage=recommendation case_id=%s run_id=%s latency_ms=%s status=%s",
        case.id,
        run.id,
        int((time.perf_counter() - started) * 1000),
        answer.case_status,
    )
    return RecommendationStage(answer=answer, run_id=run.id, message_id=message.id)


async def run_dispatch_gate(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    handoff: CaseHandoff,
    answer: AnswerView,
    source_message_id: UUID,
) -> DownstreamAgentResult | None:
    """Feature 7: gate a fresh proposal and prepare a ticket preview when safe."""
    started = time.perf_counter()
    current = await session.get(Recommendation, answer.recommendation_id)
    if not ready_to_dispatch(case.status, None if current is None else current.status):
        logger.info(
            "agent_stage skip stage=dispatch case_id=%s reason=not_ready latency_ms=%s",
            case.id,
            int((time.perf_counter() - started) * 1000),
        )
        return None

    logger.info(
        "agent_stage start stage=dispatch case_id=%s recommendation_id=%s",
        case.id,
        answer.recommendation_id,
    )
    proposal = close_proposal(handoff, answer, employee_code=case.employee_code)
    run = await start_run(session, conversation.id, source_message_id, "hr-help-dispatch")
    result = await _invoke_dispatch_graph(run, proposal)
    if result is None:
        return DownstreamAgentResult(await _packed(session, case, answer), run.id, answer.message)

    logger.info("dispatch disposition=%s hold_code=%s", result.disposition, result.hold_code or "")
    if result.disposition == "SUBMIT":
        text = await _record_dispatch_preview(session, case, conversation, answer, run)
        logger.info(
            "agent_stage end stage=dispatch case_id=%s run_id=%s latency_ms=%s disposition=%s",
            case.id,
            run.id,
            int((time.perf_counter() - started) * 1000),
            result.disposition,
        )
        return DownstreamAgentResult(await _packed(session, case, answer), run.id, text)

    note = await add_message(
        session,
        NewMessage(conversation.id, "ASSISTANT", result.reason, {"kind": "dispatch_hold", "hold_code": result.hold_code}),
    )
    finish_run(run, note.id)
    logger.info(
        "agent_stage end stage=dispatch case_id=%s run_id=%s latency_ms=%s disposition=%s hold_code=%s",
        case.id,
        run.id,
        int((time.perf_counter() - started) * 1000),
        result.disposition,
        result.hold_code or "",
    )
    return DownstreamAgentResult(await _packed(session, case, answer), run.id, result.reason)


async def _invoke_dispatch_graph(run: AgentRun, proposal: ProposalHandoff) -> DispatchResult | None:
    try:
        state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    except TypeError as exc:
        _fail_open_run(run, str(exc))
        logger.exception("dispatch rejected the proposal message")
        return None
    result = state.get("result")
    if not isinstance(result, DispatchResult):
        _fail_open_run(run, "Dispatch graph không trả kết quả.")
        return None
    return result


async def _record_dispatch_preview(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    answer: AnswerView,
    run: AgentRun,
) -> str:
    text = ask_to_send()
    note = await add_message(
        session,
        NewMessage(conversation.id, "ASSISTANT", text, {"kind": "dispatch_preview"}),
    )
    finish_run(run, note.id)
    await write_audit(
        session,
        case_id=case.id,
        actor_id=case.created_by,
        actor_role=None,
        action="DISPATCH_PREVIEW_CREATED",
        entity_type="recommendations",
        entity_id=answer.recommendation_id,
        after={"disposition": "SUBMIT"},
    )
    await notify(
        session,
        user_id=case.created_by,
        event="ASSESSMENT_READY",
        title="Báo cáo đã sẵn sàng",
        body=f"Hồ sơ {case.case_code} đã có phiếu xem trước.",
        case_id=case.id,
    )
    return text


async def _packed(session: AsyncSession, case: Case, answer: AnswerView) -> AnswerView:
    """Return the stored answer, plus the unsaved ticket when HR may still send it."""
    if case.status != answer.case_status:
        answer = answer.model_copy(update={"case_status": case.status})
    packed = await attach_packet(session, answer)
    return await with_preview(session, case, packed)


def _fail_open_run(run: AgentRun, error: str) -> None:
    """Mark a run that is still in this transaction. The caller commits."""
    run.status = "FAILED"
    run.error = error[:2000]
    run.completed_at = utc_now()
