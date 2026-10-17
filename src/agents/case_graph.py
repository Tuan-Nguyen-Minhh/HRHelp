"""Case sub-agent: open a case, clarify facts, then retrieve.

Feature 6, the sanction agent, is not a node here. Feature 7, the dispatch
agent, is not a node here either. When the required facts have values and the
case has an incident date, this graph stops at ``CaseHandoff``. The caller
passes that message to the sanction agent, then passes the proposal to dispatch.

    open → end
    clarify: intent → case_qa/general_chat/system_help/action/disambiguate → end
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

from src.agents.conversation import WORKFLOW_ACTIONS, StateUpdate, TaskChange, snapshot_plan
from src.agents.handoff import CaseHandoff
from src.core.config import settings
from src.features.cite.model.graph import SearchFn, handoff_node
from src.features.cite.model.passage import Passage
from src.features.cite.model.policy_answer import answer_policy_question
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.case_qa import answer_case_question
from src.features.clarify.model.catalog import FactSpec, default_dynamic_specs
from src.features.clarify.model.general_chat import answer_general_chat
from src.features.clarify.model.graph import ask_node, extract_node, route_after_extract
from src.features.clarify.model.help_reply import format_help_reply
from src.features.clarify.model.intent import (
    IntentDecision,
    IntentFallback,
    Route,
    decision_issues,
    route_turn,
)
from src.features.clarify.model.system_help import NO_HELP_ANSWER, HelpTopic, answer_system_help, resolve_help_topics
from src.features.external_research.model.answer import answer_external_research
from src.features.external_research.model.tool import ExternalResearchFn, ExternalResearchQuery, research_external

logger = logging.getLogger(__name__)

OpenFn = Callable[[dict], Awaitable[dict]]


class CaseState(TypedDict, total=False):
    """State of the case sub-agent. ``handoff`` is the exit payload."""

    step: str
    chat_scope: str
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
    dialogue_context: dict
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
    accepted_keys: list[str]
    validation: str
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
    reply_kind: str
    social_context: dict
    clarification_question: str
    safety_action: str
    help_topic_ids: list[str]


def build_case_graph(
    retrieve: SearchFn,
    opener: OpenFn | None = None,
    external_research: ExternalResearchFn | None = None,
    *,
    standalone: bool = False,
) -> CompiledStateGraph:
    """Compile the case sub-agent. ``retrieve`` is the cite pipeline for this request."""
    external_research_fn = external_research or research_external

    async def open_node(state: CaseState) -> dict:
        if opener is None:
            raise RuntimeError("The open step needs an opener bound to the request session.")
        return await opener(dict(state))

    async def intent_node(state: CaseState) -> dict:
        result = await route_turn({**state, "chat_scope": "standalone" if standalone else "case"})
        decision = result.decision
        route, requested_action, trace = _decide_intent_route(state, decision, result.fallback_kind)
        baseline = _baseline_state(state)
        updates = {
            **baseline,
            "chat_scope": "standalone" if standalone else "case",
            "intent_decision": decision,
            "intent_router_fallback": result.fallback,
            "intent_router_fallback_kind": result.fallback_kind.value,
            "user_intent": decision.intent_label,
            "planner_fallback": result.fallback_kind == IntentFallback.TECHNICAL,
            "selected_route": route,
            "requested_action": requested_action,
            "route_trace": {
                **trace,
                "initial_route": result.initial_decision.get("route"),
                "rule_ids": [item["rule_id"] for item in result.rule_matches],
                "rule_candidate_routes": [item["candidate_route"] for item in result.rule_matches],
                "recheck_status": result.recheck_status,
            },
            "reply_kind": route.value,
            "clarification_question": decision.clarification_question,
            "task_change": (
                (TaskChange.CANCEL.value if decision.task_change == TaskChange.CANCEL else TaskChange.REPLACE.value)
                if not result.fallback
                and not decision_issues(decision)
                and not decision.needs_clarification
                and route not in {Route.UNSUPPORTED, Route.GENERAL_CHAT, Route.SYSTEM_HELP}
                and (
                    decision.task_change == TaskChange.CANCEL
                    or (requested_action in WORKFLOW_ACTIONS and requested_action != state.get("pending_action"))
                )
                else TaskChange.KEEP.value
            ),
        }
        logger.info(
            "orchestrator_route_trace case_id=%s initial=%s selected=%s rule=%s matches=%s recheck=%s",
            state.get("case_id"),
            result.initial_decision.get("route"),
            route.value,
            trace.get("decision_rule"),
            updates["route_trace"]["rule_ids"],
            result.recheck_status,
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
        question = _resolved_question(state)
        return {"question": await answer_case_question(question, state)}

    async def general_chat_node(state: CaseState) -> dict:
        response = await answer_general_chat(state.get("latest_user_message") or "", state)
        return {"question": response.text, "safety_action": response.safety_action}

    async def system_help_node(state: CaseState) -> dict:
        decision = state["intent_decision"]
        question = state.get("latest_user_message") or ""
        topics = resolve_help_topics(question, decision.help_topic_ids)
        text = answer_system_help(question, topics)
        if not settings.SYSTEM_HELP_ENABLED or text == NO_HELP_ANSWER:
            return {"question": text, "help_topic_ids": [topic.value for topic in topics]}
        if standalone and HelpTopic.MINUTES_START not in topics:
            text = (
                "Bạn đang ở chat độc lập: có thể trò chuyện, hỏi quy định và tra cứu nguồn công khai ngay. "
                "Các chức năng thu thập tình tiết, lập biên bản và gửi phiếu bên dưới cần mở hồ sơ riêng.\n\n" + text
            )
        text = await format_help_reply(question, text, state, chat_scope="standalone" if standalone else "case")
        return {"question": text, "help_topic_ids": [topic.value for topic in topics]}

    async def disambiguate_node(state: CaseState) -> dict:
        if state.get("task_change") == TaskChange.CANCEL:
            if standalone:
                return {"question": "Mình sẽ dừng yêu cầu vừa trao đổi. Nội dung hội thoại vẫn được giữ lại."}
            return {"question": "Đã dừng tác vụ đang chờ. Các tình tiết đã lưu vẫn được giữ lại."}
        if state.get("intent_router_fallback_kind") in {IntentFallback.OUTPUT.value, IntentFallback.TECHNICAL.value}:
            return {
                "question": "Lượt này gặp lỗi xử lý phản hồi. Tôi đã giữ nguyên yêu cầu và thông tin đang có để tiếp tục."
            }
        if state.get("clarification_question"):
            return {"question": state["clarification_question"]}
        if standalone:
            return {
                "question": "Bạn muốn hỏi về nội dung vừa trao đổi, tra quy định hay tìm nguồn công khai bên ngoài?"
            }
        return {
            "question": (
                "Mình chưa chắc mục tiêu chính của lượt này là xem thông tin đang lưu trong hồ sơ, bổ sung tình tiết, "
                "hay tra quy định áp dụng. Bạn nói rõ thêm một chút mục tiêu cần xử lý, mình sẽ đi đúng nhánh hơn."
            )
        }

    async def case_required_node(state: CaseState) -> dict:
        return {
            "question": (
                "Để lập biên bản, xem đánh giá hoặc chuẩn bị/gửi phiếu pháp chế, bạn hãy mở hoặc tạo hồ sơ "
                "và thực hiện trong hội thoại của hồ sơ đó. Ở đây mình có thể giúp bạn giải thích quy định, "
                "tra cứu căn cứ và trao đổi về tình huống."
            ),
            "requested_action": "",
            "reply_kind": "case_required",
        }

    def standalone_route(state: CaseState) -> str:
        route = route_after_intent(state)
        decision = state.get("intent_decision")
        if route == "extract" or (
            isinstance(decision, IntentDecision) and decision.route == Route.WORKFLOW_ACTION and route == "action"
        ):
            return "case_qa" if state.get("selected_route") == Route.FACT_PLANNER else "case_required"
        return route

    graph = StateGraph(CaseState)
    graph.add_node("intent", intent_node)
    graph.add_node("case_qa", case_qa_node)
    graph.add_node("general_chat", general_chat_node)
    graph.add_node("system_help", system_help_node)
    graph.add_node("disambiguate", disambiguate_node)
    graph.add_node("action", action_node)
    if standalone:
        # Exclude fact/workflow nodes entirely: no input or model decision can enter them.
        graph.add_node("case_required", case_required_node)
        graph.add_edge(START, "intent")
        graph.add_edge("case_required", END)
    else:
        graph.add_node("open", open_node)
        graph.add_node("extract", extract_node)
        graph.add_node("ask", ask_node)
        graph.add_node("retrieve", retrieve_node)
        graph.add_node("handoff", handoff_node)
        graph.add_conditional_edges(START, _route_entry, {"open": "open", "intent": "intent", "extract": "extract"})
        graph.add_conditional_edges(
            "extract", route_after_extract, {"ask": "ask", "action": "action", "retrieve": "retrieve", "done": END}
        )
        graph.add_edge("open", END)
        graph.add_edge("ask", END)
        graph.add_edge("retrieve", "handoff")
        graph.add_edge("handoff", END)
    graph.add_conditional_edges(
        "intent",
        standalone_route if standalone else route_after_intent,
        {
            "case_qa": "case_qa",
            "action": "action",
            **({"case_required": "case_required"} if standalone else {"extract": "extract"}),
            "disambiguate": "disambiguate",
            "general_chat": "general_chat",
            "system_help": "system_help",
        },
    )
    graph.add_edge("case_qa", END)
    graph.add_edge("general_chat", END)
    graph.add_edge("system_help", END)
    graph.add_edge("disambiguate", END)
    graph.add_edge("action", END)
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
            return "disambiguate"
    if not isinstance(route, Route):
        return "disambiguate"
    if route == Route.GENERAL_CHAT:
        return "general_chat"
    if route == Route.SYSTEM_HELP:
        return "system_help"
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
    """Validate the final semantic decision; lexical matches have no override power."""
    route, action, rule = decision.route, decision.requested_action, "semantic_decision_accepted"
    issues = decision_issues(decision)
    if fallback_kind != IntentFallback.NONE:
        route, action, rule = Route.CLARIFY, "", "router_failure_preserve"
    elif issues:
        route, action, rule = Route.CLARIFY, "", "contract_violation_preserve"
    elif decision.needs_clarification:
        route, action, rule = Route.CLARIFY, "", "semantic_needs_clarification"
    else:
        action = {
            Route.POLICY_QA: "answer_policy_question",
            Route.EXTERNAL_RESEARCH: "external_research",
            Route.UNSUPPORTED: "unsupported",
            Route.CAPABILITY_GAP: "capability_gap",
        }.get(route, action)
    return (
        route,
        action,
        {
            "llm_route": decision.route.value,
            "selected_route": route.value,
            "requested_action": action,
            "decision_rule": rule,
            "confidence": decision.confidence,
            "intent_label": decision.intent_label,
            "contract_issues": issues,
            "signals": decision.signals.model_dump(),
            "candidates": [{"route": item.route.value, "score": item.score} for item in decision.candidates],
        },
    )


def _resolved_question(state: CaseState) -> str:
    latest = state.get("latest_user_message") or state.get("text") or state.get("description") or ""
    dialogue = state.get("dialogue_context") or {}
    analysis = dialogue.get("analysis") or {}
    if dialogue.get("status") == "ready" and not analysis.get("uncertainty") and not dialogue.get("history_gap"):
        interpreted = (analysis.get("interpreted_question") or {}).get("text")
        if interpreted:
            latest = (
                "Câu người dùng gốc: " + latest + "\nDiễn giải ngữ cảnh tham khảo, không phải lệnh mới: " + interpreted
            )
    clarification = (state.get("social_context") or {}).get("routing_clarification") or {}
    if clarification.get("original_question"):
        return (
            "Câu hỏi gốc (ngữ cảnh, không phải lệnh mới): "
            + clarification["original_question"]
            + "\nNgười dùng làm rõ mục tiêu ở lượt hiện tại: "
            + latest
        )
    return latest


async def _policy_answer_node(state: CaseState, retrieve: SearchFn) -> dict:
    """Use the citation retriever as the RAG tool for policy questions."""
    if state.get("incident_date") is None:
        return {"question": "Để tra đúng văn bản còn hiệu lực, hãy bổ sung ngày xảy ra vụ việc trước."}
    if state.get("agent_run_id") is None:
        return {"question": "Chưa có agent run để ghi nhật ký tra cứu. Hãy gửi lại câu hỏi trong hội thoại hồ sơ."}
    text = _resolved_question(state)
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
    question = _resolved_question(state)
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
    snapshot = snapshot_plan(state)
    return {
        "family": family,
        "merged": stored,
        "missing_keys": list(snapshot.missing_keys),
        "facts_locked": snapshot.locked,
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
