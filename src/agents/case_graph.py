"""Case sub-agent: open a case, clarify facts, then retrieve.

Feature 6, the sanction agent, is not a node here. When facts are confirmed
this graph stops at ``CaseHandoff``, the message that agent consumes.

    open → end
    clarify: extract → ask → end
    cite: extract → retrieve → handoff → end
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
    family: str
    merged: dict[str, StoredFact]
    missing_keys: list[str]
    facts_locked: bool
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

    graph = StateGraph(CaseState)
    graph.add_node("open", open_node)
    graph.add_node("extract", extract_node)
    graph.add_node("ask", ask_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("handoff", handoff_node)
    graph.add_conditional_edges(START, _route_entry, {"open": "open", "extract": "extract"})
    graph.add_conditional_edges(
        "extract",
        route_after_extract,
        {"ask": "ask", "retrieve": "retrieve", "done": END},
    )
    graph.add_edge("open", END)
    graph.add_edge("ask", END)
    graph.add_edge("retrieve", "handoff")
    graph.add_edge("handoff", END)
    return graph.compile()


def _route_entry(state: CaseState) -> str:
    """Open a case, or enter clarify and cite through extract."""
    if state.get("step") == "open":
        return "open"
    return "extract"
