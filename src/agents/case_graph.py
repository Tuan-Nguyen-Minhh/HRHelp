"""Case sub-agent: open a case, clarify facts, then retrieve.

Feature 6, the sanction agent, is not a node here. Feature 7, the dispatch
agent, is not a node here either. When the required facts have values and the
case has an incident date, this graph stops at ``CaseHandoff``. The caller
passes that message to the sanction agent, then passes the proposal to dispatch.

    open → end
    clarify: extract → ask → end
             extract → action → end
             extract → end
             extract → retrieve → handoff → end
    cite: extract → ask → end
          extract → retrieve → handoff → end
"""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.handoff import CaseHandoff
from src.features.cite.model.graph import SearchFn, handoff_node
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.graph import ask_node, extract_node, route_after_extract

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
    stored: dict[str, StoredFact]
    advance: bool
    semantic: bool
    family: str
    merged: dict[str, StoredFact]
    missing_keys: list[str]
    facts_locked: bool
    conflicts: list[dict]
    requested_action: str
    planner_fallback: bool
    user_intent: str
    ambiguities: list[str]
    facts: dict[str, str]
    fact_lines: list[str]
    question: str
    agent_run_id: UUID
    query: str
    hits: list[Passage]
    handoff: CaseHandoff


def build_case_graph(retrieve: SearchFn, opener: OpenFn | None = None) -> CompiledStateGraph:
    """Compile the case sub-agent. ``retrieve`` is the cite pipeline for this request."""

    async def open_node(state: CaseState) -> dict:
        if opener is None:
            raise RuntimeError("The open step needs an opener bound to the request session.")
        return await opener(dict(state))

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

    graph = StateGraph(CaseState)
    graph.add_node("open", open_node)
    graph.add_node("extract", extract_node)
    graph.add_node("ask", ask_node)
    graph.add_node("action", action_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("handoff", handoff_node)
    graph.add_conditional_edges(START, _route_entry, {"open": "open", "extract": "extract"})
    graph.add_conditional_edges(
        "extract",
        route_after_extract,
        {"ask": "ask", "action": "action", "retrieve": "retrieve", "done": END},
    )
    graph.add_edge("open", END)
    graph.add_edge("ask", END)
    graph.add_edge("action", END)
    graph.add_edge("retrieve", "handoff")
    graph.add_edge("handoff", END)
    return graph.compile()


def _route_entry(state: CaseState) -> str:
    """Open a case, or enter clarify and cite through extract."""
    if state.get("step") == "open":
        return "open"
    return "extract"


async def _policy_answer_node(state: CaseState, retrieve: SearchFn) -> dict:
    """Use the citation retriever as the RAG tool for policy questions."""
    if state.get("incident_date") is None:
        return {"question": "Để tra đúng văn bản còn hiệu lực, hãy bổ sung ngày xảy ra vụ việc trước."}
    if state.get("agent_run_id") is None:
        return {"question": "Chưa có agent run để ghi nhật ký tra cứu. Hãy gửi lại câu hỏi trong hội thoại hồ sơ."}
    text = state.get("text") or state.get("description") or ""
    query = SearchQuery(
        text=text,
        incident_date=state["incident_date"],
        agent_run_id=state["agent_run_id"],
        family=state.get("family", ""),
        fact_lines=list(state.get("fact_lines") or []),
        description=state.get("description") or "",
    )
    hits = await retrieve(query)
    return {"question": _policy_answer_text(hits), "hits": hits, "query": query.text}


def _policy_answer_text(hits: list[Passage]) -> str:
    if not hits:
        return "Chưa tìm thấy đoạn văn bản còn hiệu lực phù hợp với câu hỏi này."
    lines = ["Tìm thấy các căn cứ liên quan:"]
    for index, hit in enumerate(hits[:5], start=1):
        location = " ".join(part for part in (hit.article, hit.clause, hit.point) if part)
        label = f"{hit.policy_name}"
        if location:
            label = f"{label} - {location}"
        snippet = " ".join(hit.content.split())[:500]
        lines.append(f"{index}. {label}: {snippet}")
    lines.append("Các đoạn trên là kết quả tra cứu để HR đối chiếu; chưa phải quyết định kỷ luật.")
    return "\n".join(lines)
