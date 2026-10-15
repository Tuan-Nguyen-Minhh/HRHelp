"""Case sub-agent: open a case, clarify facts, then retrieve.

Feature 6, the sanction agent, is not a node here. Feature 7, the dispatch
agent, is not a node here either. When the required facts have values and the
case has an incident date, this graph stops at ``CaseHandoff``. The caller
passes that message to the sanction agent, then passes the proposal to dispatch.

    open → end
    clarify: intent → case_qa/action/disambiguate → end
             intent → extract → ask/action/end/retrieve → handoff → end
    cite: extract → ask → end
          extract → retrieve → handoff → end
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.conversation import WORKFLOW_ACTIONS, StateUpdate, TaskChange
from src.agents.handoff import CaseHandoff
from src.features.cite.model.graph import SearchFn, handoff_node
from src.features.cite.model.passage import Passage
from src.features.cite.model.policy_answer import answer_policy_question
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.case_qa import answer_case_question
from src.features.clarify.model.catalog import FactSpec, default_dynamic_specs
from src.features.clarify.model.graph import ask_node, extract_node, route_after_extract
from src.features.clarify.model.intent import (
    MIN_ROUTE_CONFIDENCE,
    IntentDecision,
    IntentFallback,
    IntentSignals,
    Route,
    infer_turn_signals,
    route_turn,
)
from src.features.external_research.model.answer import answer_external_research
from src.features.external_research.model.tool import ExternalResearchFn, ExternalResearchQuery, research_external

logger = logging.getLogger(__name__)

OpenFn = Callable[[dict], Awaitable[dict]]


class CaseState(TypedDict, total=False):
    """State of the case sub-agent. ``handoff`` is the exit payload."""

    step: str
    actor_id: UUID
    case_code: str
    employee_code: str
    employee_name: str | None
    description: str
    incident_date: date
    case_id: UUID
    conversation_id: UUID
    status: str
    text: str
    turn_context: str
    latest_user_message: str
    stored: dict[str, StoredFact]
    advance: bool
    semantic: bool
    family: str
    specs: list[FactSpec]
    merged: dict[str, StoredFact]
    missing_keys: list[str]
    facts_locked: bool
    locked_fact_keys: list[str]
    conflicts: list[dict]
    requested_action: str
    pending_action: str
    pending_fact_keys: list[str]
    active_specs: list[FactSpec]
    state_update: str
    task_change: str
    planner_fallback: bool
    user_intent: str
    ambiguities: list[str]
    intent_decision: IntentDecision
    intent_router_fallback: bool
    intent_router_fallback_kind: str
    selected_route: Route
    route_trace: dict
    external_sources: list[dict]
    external_research_provider: str
    facts: dict[str, str]
    fact_lines: list[str]
    question: str
    agent_run_id: UUID
    query: str
    hits: list[Passage]
    handoff: CaseHandoff


def build_case_graph(
    retrieve: SearchFn,
    opener: OpenFn | None = None,
    external_research: ExternalResearchFn | None = None,
) -> CompiledStateGraph:
    """Compile the case sub-agent. ``retrieve`` is the cite pipeline for this request."""
    external_research_fn = external_research or research_external

    async def open_node(state: CaseState) -> dict:
        if opener is None:
            raise RuntimeError("The open step needs an opener bound to the request session.")
        return await opener(dict(state))

    async def intent_node(state: CaseState) -> dict:
        result = await route_turn(state)
        decision = result.decision
        route, requested_action, trace = _decide_intent_route(state, decision, result.fallback_kind)
        baseline = _baseline_state(state)
        updates = {
            **baseline,
            "intent_decision": decision,
            "intent_router_fallback": result.fallback,
            "intent_router_fallback_kind": result.fallback_kind.value,
            "user_intent": decision.intent_label,
            "planner_fallback": result.fallback_kind == IntentFallback.TECHNICAL,
            "selected_route": route,
            "requested_action": requested_action,
            "route_trace": trace,
            "task_change": (
                (TaskChange.CANCEL.value if decision.task_change == TaskChange.CANCEL else TaskChange.REPLACE.value)
                if not result.fallback
                and decision.confidence >= MIN_ROUTE_CONFIDENCE
                and route != Route.UNSUPPORTED
                and (
                    decision.task_change == TaskChange.CANCEL
                    or (requested_action in WORKFLOW_ACTIONS and requested_action != state.get("pending_action"))
                )
                else TaskChange.KEEP.value
            ),
        }
        logger.info(
            "orchestrator_route_trace case_id=%s route=%s action=%s rule=%s llm_route=%s confidence=%s signals=%s candidates=%s",
            state.get("case_id"),
            route.value,
            requested_action,
            trace.get("decision_rule"),
            decision.route.value,
            decision.confidence,
            trace.get("signals"),
            trace.get("candidates"),
        )
        if route == Route.CAPABILITY_GAP:
            logger.info(
                "case_graph capability_gap intent=%s capability=%s confidence=%s case_id=%s",
                decision.intent_label,
                decision.capability_needed,
                decision.confidence,
                state.get("case_id"),
            )
        return updates

    async def retrieve_node(state: CaseState) -> dict:
        lines = list(state.get("fact_lines") or [])
        description = state.get("description") or ""
        text = "\n".join(part for part in (description, *lines) if part)
        query = SearchQuery(
            text=text or state.get("text") or "",
            incident_date=state["incident_date"],
            agent_run_id=state["agent_run_id"],
            family=state.get("family", ""),
            fact_lines=lines,
            description=description,
        )
        return {"hits": await retrieve(query), "query": query.text}

    async def action_node(state: CaseState) -> dict:
        action = state.get("requested_action") or ""
        if action == "answer_policy_question":
            return await _policy_answer_node(state, retrieve)
        if action == "external_research":
            return await _external_research_node(state, external_research_fn)
        if action == "capability_gap":
            decision = state.get("intent_decision")
            capability = decision.capability_needed if isinstance(decision, IntentDecision) else ""
            suffix = f" Chức năng cần thêm: {capability}." if capability else ""
            return {
                "question": (
                    "Mình hiểu nhu cầu này là hợp lý trong bối cảnh xử lý hồ sơ, nhưng hiện hệ thống chưa có "
                    "capability đủ an toàn để thực hiện trực tiếp trong luồng chat."
                    f"{suffix}"
                )
            }
        if action == "show_assessment":
            return {
                "question": (
                    "Nếu hồ sơ đã có báo cáo đánh giá, mình sẽ ưu tiên đọc và tóm tắt phần đang lưu để bạn đối chiếu. "
                    "Nếu hồ sơ chưa có báo cáo, bước phù hợp là hoàn thiện tình tiết trước, rồi yêu cầu lập biên bản "
                    "hoặc đối chiếu quy định áp dụng."
                )
            }
        return {
            "question": (
                "Yêu cầu này không thể thực hiện trong chat vì thuộc thẩm quyền phê duyệt hoặc quyết định chính thức. "
                "Mình có thể hỗ trợ làm rõ tình tiết, đối chiếu căn cứ, chuẩn bị báo cáo hoặc preview phiếu để "
                "người có thẩm quyền xem xét."
            )
        }

    async def case_qa_node(state: CaseState) -> dict:
        question = state.get("latest_user_message") or state.get("text") or ""
        return {"question": await answer_case_question(question, state)}

    async def disambiguate_node(state: CaseState) -> dict:
        if state.get("task_change") == TaskChange.CANCEL:
            return {"question": "Đã dừng tác vụ đang chờ. Các tình tiết đã lưu vẫn được giữ lại."}
        if state.get("intent_router_fallback_kind") in {IntentFallback.OUTPUT.value, IntentFallback.TECHNICAL.value}:
            return {
                "question": "Lượt này gặp lỗi xử lý phản hồi. Tôi đã giữ nguyên yêu cầu và thông tin đang có để tiếp tục."
            }
        return {
            "question": (
                "Mình chưa chắc mục tiêu chính của lượt này là xem thông tin đang lưu trong hồ sơ, bổ sung tình tiết, "
                "hay tra quy định áp dụng. Bạn nói rõ thêm một chút mục tiêu cần xử lý, mình sẽ đi đúng nhánh hơn."
            )
        }

    graph = StateGraph(CaseState)
    graph.add_node("open", open_node)
    graph.add_node("intent", intent_node)
    graph.add_node("case_qa", case_qa_node)
    graph.add_node("disambiguate", disambiguate_node)
    graph.add_node("extract", extract_node)
    graph.add_node("ask", ask_node)
    graph.add_node("action", action_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("handoff", handoff_node)
    graph.add_conditional_edges(START, _route_entry, {"open": "open", "intent": "intent", "extract": "extract"})
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {"case_qa": "case_qa", "action": "action", "extract": "extract", "disambiguate": "disambiguate"},
    )
    graph.add_conditional_edges(
        "extract",
        route_after_extract,
        {"ask": "ask", "action": "action", "retrieve": "retrieve", "done": END},
    )
    graph.add_edge("open", END)
    graph.add_edge("case_qa", END)
    graph.add_edge("disambiguate", END)
    graph.add_edge("ask", END)
    graph.add_edge("action", END)
    graph.add_edge("retrieve", "handoff")
    graph.add_edge("handoff", END)
    return graph.compile()


def _route_entry(state: CaseState) -> str:
    """Open a case, or enter clarify and cite through extract."""
    if state.get("step") == "open":
        return "open"
    if state.get("step") == "cite" or bool(state.get("advance")) or not state.get("semantic"):
        return "extract"
    return "intent"


def route_after_intent(state: CaseState) -> str:
    """Route from the intent decision. Python keeps final control."""
    if state.get("task_change") == TaskChange.CANCEL:
        return "disambiguate"
    route = state.get("selected_route")
    if not isinstance(route, Route):
        decision = state.get("intent_decision")
        if isinstance(decision, IntentDecision):
            route, _, _ = _decide_intent_route(
                state, decision, IntentFallback(state.get("intent_router_fallback_kind") or IntentFallback.NONE)
            )
        elif state.get("intent_router_fallback_kind") == IntentFallback.TECHNICAL.value:
            return "extract"
    if not isinstance(route, Route):
        return "disambiguate"
    if route == Route.CASE_QA:
        return "case_qa"
    if route == Route.POLICY_QA:
        return "action"
    if route == Route.FACT_PLANNER:
        return "extract"
    if route == Route.WORKFLOW_ACTION:
        decision = state.get("intent_decision")
        if not isinstance(decision, IntentDecision):
            return "disambiguate"
        return (
            "extract" if decision.requires_fact_planner or decision.requested_action in WORKFLOW_ACTIONS else "action"
        )
    if route in {Route.EXTERNAL_RESEARCH, Route.UNSUPPORTED, Route.CAPABILITY_GAP}:
        return "action"
    if route == Route.CLARIFY:
        return "disambiguate"
    return "disambiguate"


def _decide_intent_route(
    state: CaseState,
    decision: IntentDecision,
    fallback_kind: IntentFallback,
) -> tuple[Route, str, dict]:
    """Select the final route with deterministic priority rules."""
    signals = _merge_signals(decision.signals, infer_turn_signals(state))
    candidates = [
        {"route": item.route.value, "score": item.score, "evidence": item.evidence} for item in decision.candidates
    ]
    selected = Route.CLARIFY
    requested_action = ""
    rule = "default_clarify"
    rejected: list[dict[str, str]] = []
    waiting = bool(state.get("pending_fact_keys", state.get("locked_fact_keys")))
    latest = state.get("latest_user_message", state.get("text")) or ""

    if fallback_kind == IntentFallback.OUTPUT:
        selected = Route.FACT_PLANNER if waiting and latest else Route.CLARIFY
        rule = (
            "output_failure_revalidate_pending_reply" if selected == Route.FACT_PLANNER else "output_failure_preserve"
        )
    elif fallback_kind == IntentFallback.TECHNICAL:
        selected = Route.FACT_PLANNER
        rule = "technical_fallback_to_fact_planner"
    elif fallback_kind == IntentFallback.SEMANTIC:
        selected = Route.CLARIFY
        rule = "semantic_fallback_to_clarify"
    elif signals.asks_prohibited_action or decision.route == Route.UNSUPPORTED:
        selected = Route.UNSUPPORTED
        requested_action = "unsupported"
        rule = "prohibited_action_priority"
    elif signals.asks_external_public_source or signals.asks_latest_info or decision.requires_external_research:
        selected = Route.EXTERNAL_RESEARCH
        requested_action = "external_research"
        rule = "external_public_latest_priority"
        if decision.route != Route.EXTERNAL_RESEARCH:
            rejected.append({"route": decision.route.value, "reason": "external/latest signal has higher priority"})
    elif decision.confidence < MIN_ROUTE_CONFIDENCE:
        selected = Route.FACT_PLANNER if waiting and latest else Route.CLARIFY
        rule = "low_confidence_validate_pending_reply" if selected == Route.FACT_PLANNER else "low_confidence_clarify"
    elif decision.route == Route.CAPABILITY_GAP:
        selected = Route.CAPABILITY_GAP
        requested_action = "capability_gap"
        rule = "capability_gap_from_llm"
    elif signals.asks_workflow_action or decision.route == Route.WORKFLOW_ACTION:
        selected = Route.WORKFLOW_ACTION
        requested_action = decision.requested_action
        rule = "workflow_action_priority"
    elif signals.updates_case_fact or decision.route == Route.FACT_PLANNER:
        selected = Route.FACT_PLANNER
        rule = "case_fact_update_priority"
    elif signals.asks_internal_policy or decision.requires_internal_retrieval or decision.route == Route.POLICY_QA:
        selected = Route.POLICY_QA
        requested_action = "answer_policy_question"
        rule = "internal_policy_priority"
    elif signals.asks_case_memory or decision.route == Route.CASE_QA:
        selected = Route.CASE_QA
        rule = "case_memory_priority"
    elif decision.route == Route.CLARIFY:
        selected = Route.CLARIFY
        rule = "llm_clarify"
    else:
        selected = decision.route
        rule = "llm_route_fallback"

    trace = {
        "llm_route": decision.route.value,
        "selected_route": selected.value,
        "requested_action": requested_action,
        "decision_rule": rule,
        "confidence": decision.confidence,
        "intent_label": decision.intent_label,
        "signals": signals.model_dump(),
        "candidates": candidates,
        "rejected_routes": rejected,
    }
    return selected, requested_action, trace


def _merge_signals(left: IntentSignals, right: IntentSignals) -> IntentSignals:
    return IntentSignals(
        asks_external_public_source=left.asks_external_public_source or right.asks_external_public_source,
        asks_latest_info=left.asks_latest_info or right.asks_latest_info,
        asks_internal_policy=left.asks_internal_policy or right.asks_internal_policy,
        updates_case_fact=left.updates_case_fact or right.updates_case_fact,
        asks_workflow_action=left.asks_workflow_action or right.asks_workflow_action,
        asks_case_memory=left.asks_case_memory or right.asks_case_memory,
        asks_prohibited_action=left.asks_prohibited_action or right.asks_prohibited_action,
    )


async def _policy_answer_node(state: CaseState, retrieve: SearchFn) -> dict:
    """Use the citation retriever as the RAG tool for policy questions."""
    if state.get("incident_date") is None:
        return {"question": "Để tra đúng văn bản còn hiệu lực, hãy bổ sung ngày xảy ra vụ việc trước."}
    if state.get("agent_run_id") is None:
        return {"question": "Chưa có agent run để ghi nhật ký tra cứu. Hãy gửi lại câu hỏi trong hội thoại hồ sơ."}
    text = state.get("latest_user_message") or state.get("text") or state.get("description") or ""
    query = SearchQuery(
        text=text,
        incident_date=state["incident_date"],
        agent_run_id=state["agent_run_id"],
        family=state.get("family", ""),
        fact_lines=list(state.get("fact_lines") or []),
        description=state.get("description") or "",
    )
    hits = await retrieve(query)
    text = await answer_policy_question(query.text, hits, description=query.description)
    return {"question": text, "hits": hits, "query": query.text}


async def _external_research_node(state: CaseState, external_research: ExternalResearchFn) -> dict:
    """Call the configured external research MCP/search tool."""
    question = state.get("latest_user_message") or state.get("text") or state.get("description") or ""
    research_question = _external_research_question(state, question)
    query = ExternalResearchQuery(
        question=research_question,
        description=state.get("description") or "",
    )
    result = await external_research(query)
    text = await answer_external_research(question, result, description=query.description)
    return {
        "question": text,
        "query": result.query,
        "external_sources": [source.model_dump() for source in result.sources],
        "external_research_provider": result.provider,
    }


def _external_research_question(state: CaseState, question: str) -> str:
    """Build a scoped public-source query instead of sending a vague chat turn."""
    description = (state.get("description") or "").strip()
    fact_lines = [str(item).strip() for item in state.get("fact_lines") or [] if str(item).strip()]
    context_parts = []
    if description:
        context_parts.append(f"Mô tả hồ sơ: {description}")
    if fact_lines:
        context_parts.append("Tình tiết đã xác nhận: " + "; ".join(fact_lines[:8]))
    context = "\n".join(context_parts)
    return (
        "Tra cứu nguồn công khai chính thống của Việt Nam về pháp luật lao động và quy trình xử lý kỷ luật lao động.\n"
        f"Câu hỏi HR: {question.strip() or '(không có câu hỏi cụ thể)'}\n"
        f"{context}\n"
        "Tập trung vào: Bộ luật Lao động, nghị định hướng dẫn, trình tự xử lý kỷ luật lao động, "
        "hồ sơ/chứng cứ, biên bản, yêu cầu giải trình, bảo mật thông tin khách hàng hoặc hành vi vi phạm liên quan. "
        "Loại bỏ kết quả không liên quan đến lao động, kỷ luật lao động, tranh chấp lao động hoặc quy trình HR."
    )


def _baseline_state(state: CaseState) -> dict:
    stored = state.get("stored") or {}
    family = state.get("family") or "GENERAL"
    return {
        "family": family,
        "merged": stored,
        "missing_keys": list(state.get("pending_fact_keys") or []),
        "facts_locked": False,
        "conflicts": [],
        "requested_action": "",
        "planner_fallback": False,
        "user_intent": "",
        "ambiguities": [],
        "validation": "ok",
        "accepted_keys": [],
        "specs": list(state.get("active_specs") or default_dynamic_specs(family, set(stored))),
        "state_update": StateUpdate.PRESERVE.value,
    }
