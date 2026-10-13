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

from src.agents.handoff import CaseHandoff
from src.features.cite.model.graph import SearchFn, handoff_node
from src.features.cite.model.passage import Passage
from src.features.cite.model.policy_answer import answer_policy_question
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.case_qa import answer_case_question
from src.features.clarify.model.catalog import FactSpec, default_dynamic_specs
from src.features.clarify.model.graph import ask_node, extract_node, route_after_extract
from src.features.clarify.model.intent import MIN_ROUTE_CONFIDENCE, IntentDecision, IntentFallback, Route, route_turn
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
    planner_fallback: bool
    user_intent: str
    ambiguities: list[str]
    intent_decision: IntentDecision
    intent_router_fallback: bool
    intent_router_fallback_kind: str
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
        baseline = _baseline_state(state)
        updates = {
            **baseline,
            "intent_decision": decision,
            "intent_router_fallback": result.fallback,
            "intent_router_fallback_kind": result.fallback_kind.value,
            "user_intent": decision.intent_label,
            "planner_fallback": result.fallback_kind == IntentFallback.TECHNICAL,
        }
        if decision.route == Route.POLICY_QA:
            updates["requested_action"] = "answer_policy_question"
        elif decision.route == Route.WORKFLOW_ACTION:
            updates["requested_action"] = decision.requested_action
        elif decision.route == Route.EXTERNAL_RESEARCH:
            updates["requested_action"] = "external_research"
        elif decision.route == Route.CAPABILITY_GAP:
            logger.info(
                "case_graph capability_gap intent=%s capability=%s confidence=%s case_id=%s",
                decision.intent_label,
                decision.capability_needed,
                decision.confidence,
                state.get("case_id"),
            )
            updates["requested_action"] = "capability_gap"
        elif decision.route == Route.UNSUPPORTED:
            updates["requested_action"] = "unsupported"
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
                    "Yêu cầu này hợp lý nhưng hệ thống hiện chưa có capability an toàn để xử lý trong luồng chat."
                    f"{suffix}"
                )
            }
        if action == "show_assessment":
            return {
                "question": (
                    "Nếu hồ sơ đã có báo cáo, hệ thống sẽ đọc báo cáo hiện tại từ bước trả lời. "
                    "Nếu chưa có báo cáo, hãy yêu cầu lập biên bản hoặc đối chiếu quy định sau khi đủ tình tiết."
                )
            }
        return {
            "question": (
                "Yêu cầu này không thể thực hiện trong chat. Agent chỉ làm rõ tình tiết, "
                "đối chiếu căn cứ, lập báo cáo/preview phiếu và giữ bước duyệt cho người có thẩm quyền."
            )
        }

    async def case_qa_node(state: CaseState) -> dict:
        question = state.get("latest_user_message") or state.get("text") or ""
        return {"question": await answer_case_question(question, state)}

    async def disambiguate_node(state: CaseState) -> dict:
        return {
            "question": (
                "Mình chưa chắc bạn muốn hỏi thông tin đang lưu trong hồ sơ, bổ sung tình tiết, "
                "hay tra quy định áp dụng. Bạn hãy nói rõ mục tiêu của lượt này."
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
    if state.get("intent_router_fallback_kind") == IntentFallback.TECHNICAL.value:
        return "extract"
    if state.get("intent_router_fallback_kind") == IntentFallback.SEMANTIC.value:
        return "disambiguate"
    decision = state.get("intent_decision")
    if not isinstance(decision, IntentDecision):
        return "disambiguate"
    if decision.confidence < MIN_ROUTE_CONFIDENCE:
        return "disambiguate"
    if decision.route == Route.CASE_QA:
        return "case_qa"
    if decision.route == Route.POLICY_QA:
        return "action"
    if decision.route == Route.FACT_PLANNER:
        return "extract"
    if decision.route == Route.WORKFLOW_ACTION:
        return "extract" if decision.requires_fact_planner else "action"
    if decision.route in {Route.EXTERNAL_RESEARCH, Route.UNSUPPORTED, Route.CAPABILITY_GAP}:
        return "action"
    if decision.route == Route.CLARIFY:
        return "disambiguate"
    return "disambiguate"


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
    query = ExternalResearchQuery(
        question=question,
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


def _baseline_state(state: CaseState) -> dict:
    stored = state.get("stored") or {}
    family = state.get("family") or "GENERAL"
    return {
        "family": family,
        "merged": stored,
        "missing_keys": [],
        "facts_locked": False,
        "conflicts": [],
        "requested_action": "",
        "planner_fallback": False,
        "user_intent": "",
        "ambiguities": [],
        "validation": "ok",
        "accepted_keys": [],
        "specs": list(default_dynamic_specs(family, set(stored))),
    }


