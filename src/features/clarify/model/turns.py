"""Clarify a case in chat, then cite once HR confirms the facts."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.case_graph import build_case_graph
from src.agents.handoff import CaseHandoff
from src.agents.runs import finish_run, mark_run_failed, start_run
from src.common.access import require_case, require_mutable_case
from src.common.audit import write_audit
from src.common.clock import utc_now
from src.common.errors import AppError
from src.common.notify import notify
from src.features.answer.model.answers import attach_packet, load, withdraw
from src.features.answer.model.dispatch import DispatchResult, build_dispatch_agent, ready_to_dispatch
from src.features.answer.model.proposal import close_proposal
from src.features.answer.model.send import ask_to_send, with_preview
from src.features.answer.schema import AnswerView
from src.features.cite.model.search import search_policies
from src.features.clarify.model.assess import ClarifyPlan, FactConflict, StoredFact, build_question
from src.features.clarify.model.catalog import OPTIONAL_FACT_KEYS, required_specs
from src.features.clarify.model.multi_agent import run_dispatch_gate, run_downstream_agents, run_recommendation_agent
from src.features.clarify.model.store import (
    FactWrite,
    NewMessage,
    add_message,
    list_fact_rows,
    list_user_text,
    save_extracted,
    write_fact,
)
from src.features.clarify.schema import (
    ConfirmFactsRequest,
    FactConfirmItem,
    FactListResponse,
    SendMessageRequest,
    TurnResponse,
)
from src.features.clarify.schema.present import present_facts
from src.features.opencase.model.cases import active_conversation
from src.models.agent_runs import AgentRun
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.recommendations import Recommendation
from src.models.users import User

logger = logging.getLogger(__name__)

_PIPELINE = "hr-help-rules"
_LOCKED = (
    "Tình tiết bắt buộc đã được khóa. Câu trả lời đã lưu vẫn giữ. "
    "Muốn sửa một fact, hãy gửi giá trị mới qua xác nhận tình tiết."
)
_NEED_PUBLISH = "Đã đủ tình tiết nhưng hồ sơ chưa có ngày xảy ra việc nên chưa đối chiếu được."
_DIRECT_ACTIONS = {"answer_policy_question", "unsupported"}


async def handle_message(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: SendMessageRequest,
) -> TurnResponse:
    """Store the user message, extract facts, and ask for whatever is still open."""
    case = await require_mutable_case(session, case_id, actor)
    conversation = await _conversation(session, case.id)
    message = await add_message(session, NewMessage(conversation.id, "USER", payload.content))
    run = await start_run(session, conversation.id, message.id, _PIPELINE)
    await session.commit()
    try:
        return await _clarify(session, case, conversation, run, message.id, actor.id)
    except Exception as exc:
        await _fail(session, run.id, exc)
        if isinstance(exc, AppError):
            raise
        raise AppError(500, "Không xử lý được lượt chat. Hồ sơ giữ nguyên trạng thái trước đó.") from exc


async def confirm_facts(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: ConfirmFactsRequest,
) -> TurnResponse:
    """Confirm facts. A complete set runs retrieval and stores the answer.

    The fact update and the answer commit together. A failed search leaves the
    case unchanged, and HR can confirm again.
    """
    case = await require_mutable_case(session, case_id, actor)
    conversation = await _conversation(session, case.id)
    try:
        response = await _confirm(session, actor, case, conversation, payload.facts)
        await session.commit()
    except AppError:
        await session.rollback()
        raise
    except Exception as exc:
        logger.exception("confirm failed")
        await session.rollback()
        raise AppError(500, "Không chốt được câu trả lời. Hồ sơ chưa đổi.") from exc
    return response


async def list_facts(session: AsyncSession, actor: User, case_id: UUID) -> FactListResponse:
    """Project stored facts plus values already readable from the narrative."""
    case = await require_case(session, case_id, actor)
    conversation = await active_conversation(session, case.id)
    conversation_id = conversation.id if conversation else None
    plan, _handoff = await _plan(session, case, conversation_id)
    return FactListResponse(
        case_id=case.id,
        case_status=case.status,
        family=plan.family,
        facts=present_facts(plan.family, plan.merged),
        missing_fact_keys=plan.missing_keys,
        facts_locked=plan.locked,
    )


async def _clarify(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    run: AgentRun,
    source_id: UUID,
    actor_id: UUID,
) -> TurnResponse:
    plan, handoff = await _planned(
        session, case, conversation.id, source_id, semantic=True, actor_id=actor_id, run_id=run.id
    )
    if handoff is not None:
        note = _cited_text(handoff)
        assistant = await add_message(session, NewMessage(conversation.id, "ASSISTANT", note, {"kind": "handoff"}))
        finish_run(run, assistant.id)
        downstream = await run_downstream_agents(session, case, conversation, handoff, assistant.id)
        await session.commit()
        return _turn(
            case,
            conversation.id,
            plan,
            downstream.assistant_text,
            downstream.answer,
            handoff,
            downstream.agent_run_id,
        )
    if plan.requested_action == "show_assessment":
        answer = await load(session, case)
        text = answer.message if answer is not None else "Hồ sơ chưa có báo cáo đánh giá để hiển thị."
    elif plan.requested_action in _DIRECT_ACTIONS and plan.question:
        answer = None
        text = plan.question
    elif plan.locked:
        answer = await load(session, case)
        text = _LOCKED if answer is not None else _NEED_PUBLISH
    else:
        await _reopen(session, case)
        answer = None
        text = _question(plan)
    assistant = await add_message(session, NewMessage(conversation.id, "ASSISTANT", text, {"kind": "clarify"}))
    finish_run(run, assistant.id)
    await session.commit()
    return _turn(case, conversation.id, plan, text, answer, None, run.id)


async def _confirm(
    session: AsyncSession,
    actor: User,
    case: Case,
    conversation: Conversation,
    items: list[FactConfirmItem],
) -> TurnResponse:
    plan, _handoff = await _plan(session, case, conversation.id)
    stored = await _stored(session, case.id)
    _check_keys(plan.family, items)
    if not _changed(stored, plan.merged, items):
        return await _unchanged(session, case, conversation, plan)
    await _apply(session, actor.id, case.id, stored, plan.merged, items)
    plan, _handoff = await _planned(session, case, conversation.id, None)
    if not plan.locked:
        await _reopen(session, case)
        question = _question(plan)
        await add_message(session, NewMessage(conversation.id, "ASSISTANT", question, {"kind": "clarify"}))
        return _turn(case, conversation.id, plan, question, None, None, None)
    return await _cite(session, case, conversation, plan)


async def _unchanged(session: AsyncSession, case: Case, conversation: Conversation, plan: ClarifyPlan) -> TurnResponse:
    if not plan.locked:
        question = _question(plan)
        return _turn(case, conversation.id, plan, question, None, None, None)
    existing = await load(session, case)
    if existing is not None:
        current = await session.get(Recommendation, existing.recommendation_id)
        if current is not None and current.status == "DRAFT":
            return _turn(case, conversation.id, plan, _LOCKED, existing, None, existing.agent_run_id)
    return await _cite(session, case, conversation, plan)


async def _cite(session: AsyncSession, case: Case, conversation: Conversation, plan: ClarifyPlan) -> TurnResponse:
    """Run cite, then pass its locked handoff to the recommendation agent."""
    if case.incident_date is None:
        raise AppError(422, "Hồ sơ chưa có ngày xảy ra việc nên chưa đối chiếu được văn bản.")
    facts = _locked_facts(plan)
    text = await _transcript(session, case, conversation.id)
    system = await add_message(
        session, NewMessage(conversation.id, "SYSTEM", _confirmed_text(facts), {"kind": "facts_confirmed"})
    )
    run = await start_run(session, conversation.id, system.id, "hr-help-retrieval")
    graph = build_case_graph(lambda query: search_policies(session, query))
    state = await graph.ainvoke(
        {
            "step": "cite",
            "text": text,
            "stored": {key: StoredFact(value, True) for key, value in facts.items()},
            "description": case.description or "",
            "incident_date": case.incident_date,
            "employee_name": case.employee_name,
            "employee_code": case.employee_code,
            "agent_run_id": run.id,
            "case_id": case.id,
        }
    )
    message = state.get("handoff")
    if not isinstance(message, CaseHandoff):
        raise AppError(422, "Tình tiết chưa khóa nên chưa đối chiếu văn bản.")
    note = _cited_text(message)
    assistant = await add_message(session, NewMessage(conversation.id, "ASSISTANT", note, {"kind": "handoff"}))
    finish_run(run, assistant.id)
    downstream = await run_downstream_agents(session, case, conversation, message, assistant.id)
    return _turn(
        case,
        conversation.id,
        plan,
        downstream.assistant_text,
        downstream.answer,
        message,
        downstream.agent_run_id,
    )


async def _recommend(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    message: CaseHandoff,
    source_id: UUID,
) -> tuple[AnswerView, UUID, str]:
    """Compatibility wrapper for the downstream recommendation workflow."""
    recommendation = await run_recommendation_agent(session, case, conversation, message, source_id)
    dispatched = await run_dispatch_gate(session, case, conversation, message, recommendation.answer, recommendation.message_id)
    if dispatched is not None:
        return dispatched.answer, dispatched.agent_run_id, dispatched.assistant_text
    return recommendation.answer, recommendation.run_id, recommendation.answer.message


async def _dispatch(
    session: AsyncSession,
    case: Case,
    conversation: Conversation,
    message: CaseHandoff,
    answer: AnswerView,
    source_id: UUID,
) -> tuple[AnswerView, UUID | None, str]:
    """Legacy test hook for dispatch. Runtime code uses ``multi_agent``."""
    current = await session.get(Recommendation, answer.recommendation_id)
    if not ready_to_dispatch(case.status, None if current is None else current.status):
        return await _packed(session, case, answer), None, answer.message
    proposal = close_proposal(message, answer, employee_code=case.employee_code)
    run = await start_run(session, conversation.id, source_id, "hr-help-dispatch")
    try:
        state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    except TypeError as exc:
        _fail_open_run(run, str(exc))
        logger.exception("dispatch rejected the proposal message")
        return await _packed(session, case, answer), run.id, answer.message
    result = state.get("result")
    if not isinstance(result, DispatchResult):
        _fail_open_run(run, "Dispatch graph không trả kết quả.")
        return await _packed(session, case, answer), run.id, answer.message
    logger.info("dispatch disposition=%s hold_code=%s", result.disposition, result.hold_code or "")
    if result.disposition == "SUBMIT":
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
        return await _packed(session, case, answer), run.id, text
    kind = "dispatch_hold"
    metadata = {"kind": kind, "hold_code": result.hold_code}
    note = await add_message(session, NewMessage(conversation.id, "ASSISTANT", result.reason, metadata))
    finish_run(run, note.id)
    return await _packed(session, case, answer), run.id, result.reason


async def _packed(session: AsyncSession, case: Case, answer: AnswerView) -> AnswerView:
    """Legacy test hook for attaching ticket previews."""
    if case.status != answer.case_status:
        answer = answer.model_copy(update={"case_status": case.status})
    packed = await attach_packet(session, answer)
    return await with_preview(session, case, packed)


def _fail_open_run(run: AgentRun, error: str) -> None:
    """Mark a run that is still in this transaction. The caller commits."""
    run.status = "FAILED"
    run.error = error[:2000]
    run.completed_at = utc_now()


async def _planned(
    session: AsyncSession,
    case: Case,
    conversation_id: UUID,
    source_id: UUID | None,
    *,
    semantic: bool = False,
    actor_id: UUID | None = None,
    run_id: UUID | None = None,
) -> tuple[ClarifyPlan, CaseHandoff | None]:
    """Extract, then persist new unconfirmed values before the caller commits."""
    plan, handoff = await _plan(session, case, conversation_id, semantic=semantic, run_id=run_id)
    stored = await _stored(session, case.id)
    await _persist_extracted(session, case.id, stored, plan.merged, source_id, actor_id)
    return plan, handoff


async def _plan(
    session: AsyncSession,
    case: Case,
    conversation_id: UUID | None,
    *,
    semantic: bool = False,
    run_id: UUID | None = None,
) -> tuple[ClarifyPlan, CaseHandoff | None]:
    text = await _transcript(session, case, conversation_id)
    stored = await _stored(session, case.id)
    graph = build_case_graph(lambda query: search_policies(session, query))
    state = await graph.ainvoke(
        {
            "step": "clarify",
            "text": text,
            "stored": stored,
            "description": case.description or "",
            "semantic": semantic,
            "incident_date": case.incident_date,
            "employee_name": case.employee_name,
            "employee_code": case.employee_code,
            "agent_run_id": run_id,
            "case_id": case.id,
        }
    )
    message = state.get("handoff")
    handoff = message if isinstance(message, CaseHandoff) else None
    plan = ClarifyPlan(
        state["family"],
        state["merged"],
        list(state.get("missing_keys") or []),
        bool(state["facts_locked"]),
        state.get("question") or "",
        _conflicts(state.get("conflicts")),
        state.get("requested_action") or "",
        bool(state.get("planner_fallback")),
        state.get("user_intent") or "",
        tuple(state.get("ambiguities") or []),
        state.get("validation") or "ok",
        tuple(state.get("accepted_keys") or []),
    )
    return plan, handoff


def _turn(
    case: Case,
    conversation_id: UUID,
    plan: ClarifyPlan,
    assistant_text: str,
    answer: AnswerView | None,
    handoff: CaseHandoff | None,
    run_id: UUID | None,
) -> TurnResponse:
    return TurnResponse(
        case_id=case.id,
        case_status=case.status,
        conversation_id=conversation_id,
        family=plan.family,
        assistant_message=assistant_text,
        facts=present_facts(plan.family, plan.merged),
        missing_fact_keys=plan.missing_keys,
        facts_locked=plan.locked,
        answer=answer,
        handoff=handoff,
        agent_run_id=run_id,
    )


def _question(plan: ClarifyPlan) -> str:
    """Use the ask node's text. Rebuild it only when that node did not run."""
    if plan.question:
        return plan.question
    return build_question(plan.family, plan.missing_keys, plan.merged)


def _cited_text(message: CaseHandoff) -> str:
    """Status line for HR. The structured payload is ``handoff``, not this sentence."""
    if message.retrieval == "empty" or not message.passages:
        return (
            "Không tìm thấy đoạn còn hiệu lực cho hồ sơ này. "
            "Chưa lập căn cứ trích dẫn. Message để trống phần văn bản cho agent đề xuất chế tài."
        )
    if message.retrieval == "page_index":
        lead = (
            f"Tìm theo từ khóa không ra đoạn. Đã lấy {len(message.passages)} đầu điều "
            "từ mục lục văn bản còn hiệu lực vào ngày vụ việc. "
        )
    else:
        lead = f"Đã đối chiếu {len(message.passages)} đoạn còn hiệu lực vào ngày vụ việc. "
    gap = " Chưa có nội quy còn hiệu lực trong các đoạn giữ lại." if message.missing_internal_rule else ""
    return f"{lead}Message đã sẵn sàng cho agent đề xuất chế tài.{gap}"


async def _reopen(session: AsyncSession, case: Case) -> None:
    before = case.status
    if before == "ANALYZED":
        await withdraw(session, case.id)
    if before == "NEED_INFO":
        return
    from src.common.workflow import assert_transition

    assert_transition(before, "NEED_INFO")
    case.status = "NEED_INFO"
    await write_audit(
        session,
        case_id=case.id,
        actor_id=case.created_by,
        actor_role=None,
        action="FACT_CHANGED",
        entity_type="cases",
        entity_id=case.id,
        before={"status": before},
        after={"status": "NEED_INFO"},
    )
    await notify(
        session,
        user_id=case.created_by,
        event="CASE_NEEDS_INFO",
        title="Hồ sơ cần thêm tình tiết",
        body=f"Hồ sơ {case.case_code} cần bổ sung tình tiết.",
        case_id=case.id,
    )


async def _persist_extracted(
    session: AsyncSession,
    case_id: UUID,
    stored: dict[str, StoredFact],
    merged: dict[str, StoredFact],
    source_id: UUID | None,
    actor_id: UUID | None = None,
) -> None:
    for key, item in merged.items():
        current = stored.get(key)
        if item.confirmed:
            if actor_id is None:
                continue
            if current is None or current.value != item.value or not current.confirmed:
                await write_fact(session, FactWrite(case_id, key, item.value, True, actor_id, source_id))
            continue
        if current is not None and (current.confirmed or current.value == item.value):
            continue
        await save_extracted(session, FactWrite(case_id, key, item.value, False, None, source_id))


def _conflicts(raw: list[dict] | None) -> tuple[FactConflict, ...]:
    found = []
    for item in raw or []:
        found.append(
            FactConflict(
                key=item["key"],
                confirmed_value=item["confirmed_value"],
                proposed_value=item["proposed_value"],
                evidence=item.get("evidence", ""),
            )
        )
    return tuple(found)


async def _apply(
    session: AsyncSession,
    actor_id: UUID,
    case_id: UUID,
    stored: dict[str, StoredFact],
    projected: dict[str, StoredFact],
    items: list[FactConfirmItem],
) -> None:
    for item in items:
        value = _value(item, stored, projected)
        if not value:
            raise AppError(422, f"Tình tiết {item.fact_key} chưa có giá trị.")
        actor = actor_id if item.confirmed else None
        await write_fact(session, FactWrite(case_id, item.fact_key, value, item.confirmed, actor))
        await write_audit(
            session,
            case_id=case_id,
            actor_id=actor_id,
            actor_role=None,
            action="FACT_CONFIRMED" if item.confirmed else "FACT_CHANGED",
            entity_type="case_facts",
            entity_id=case_id,
            after={"fact_key": item.fact_key, "confirmed": item.confirmed},
        )


def _changed(stored: dict[str, StoredFact], projected: dict[str, StoredFact], items: list[FactConfirmItem]) -> bool:
    for item in items:
        value = _value(item, stored, projected)
        current = stored.get(item.fact_key)
        if current is None or current.value != value or current.confirmed != item.confirmed:
            return True
    return False


def _value(item: FactConfirmItem, stored: dict[str, StoredFact], projected: dict[str, StoredFact]) -> str | None:
    if item.fact_value:
        return item.fact_value
    current = stored.get(item.fact_key)
    if current is not None and current.value:
        return current.value
    suggested = projected.get(item.fact_key)
    if suggested is not None and suggested.value:
        return suggested.value
    return None


def _check_keys(family: str, items: list[FactConfirmItem]) -> None:
    allowed = {spec.key for spec in required_specs(family)} | set(OPTIONAL_FACT_KEYS)
    for item in items:
        if item.fact_key not in allowed:
            raise AppError(422, "Tình tiết không thuộc bộ fact của vụ này.", code="FACT_NOT_ALLOWED")


def _locked_facts(plan: ClarifyPlan) -> dict[str, str]:
    facts = {spec.key: plan.merged[spec.key].value for spec in required_specs(plan.family)}
    for key in OPTIONAL_FACT_KEYS:
        item = plan.merged.get(key)
        if item is not None and item.confirmed and item.value:
            facts[key] = item.value
    return facts


def _confirmed_text(facts: dict[str, str]) -> str:
    body = "\n".join(f"{key}={value}" for key, value in facts.items())
    return f"Đã xác nhận tình tiết:\n{body}"


async def _conversation(session: AsyncSession, case_id: UUID) -> Conversation:
    conversation = await active_conversation(session, case_id)
    if conversation is None:
        raise AppError(409, "Hồ sơ chưa có hội thoại đang mở.")
    return conversation


async def _transcript(session: AsyncSession, case: Case, conversation_id: UUID | None) -> str:
    spoken = await list_user_text(session, conversation_id) if conversation_id else ""
    return "\n".join(part for part in (case.description or "", spoken) if part)


async def _stored(session: AsyncSession, case_id: UUID) -> dict[str, StoredFact]:
    rows = await list_fact_rows(session, case_id)
    stored = {}
    for row in rows:
        if row.fact_value:
            stored[row.fact_key] = StoredFact(value=row.fact_value, confirmed=bool(row.confirmed))
    return stored


async def _fail(session: AsyncSession, run_id: UUID, exc: Exception) -> None:
    logger.exception("clarify turn failed")
    await session.rollback()
    await mark_run_failed(session, run_id, str(exc))
    await session.commit()
