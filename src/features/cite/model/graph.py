"""Retrieve node and the handoff the intake agent sends onward.

Cite does not choose a sanction. It returns passages inside ``CaseHandoff``.
"""

from collections.abc import Awaitable, Callable

from src.agents.handoff import CaseHandoff, CitedPassage
from src.features.cite.model.page_index import retrieval_mode
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery

SearchFn = Callable[[SearchQuery], Awaitable[list[Passage]]]


def retrieve_node(search: SearchFn):
    """Search policy versions that were in force on the incident date."""

    async def retrieve(state: dict) -> dict:
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
        return {"hits": await search(query), "query": query.text}

    return retrieve


def handoff_node(state: dict) -> dict:
    """Pack confirmed facts and cited passages into the shared message."""
    hits = list(state.get("hits") or [])
    passages = [_cited(hit) for hit in hits]
    message = CaseHandoff(
        case_id=state.get("case_id"),
        employee_code=state.get("employee_code"),
        incident_date=state["incident_date"],
        employee_name=state.get("employee_name"),
        description=state.get("description") or "",
        family=state.get("family") or "",
        facts=dict(state.get("facts") or {}),
        fact_lines=list(state.get("fact_lines") or []),
        passages=passages,
        missing_internal_rule=not any(item.policy_type == "INTERNAL_RULE" for item in passages),
        agent_run_id=state["agent_run_id"],
        query=state.get("query") or "",
        retrieval=retrieval_mode(hits),
    )
    return {"handoff": message}


def _cited(hit: Passage) -> CitedPassage:
    return CitedPassage(
        chunk_id=hit.chunk_id,
        policy_version_id=hit.policy_version_id,
        content=hit.content,
        article=hit.article,
        clause=hit.clause,
        point=hit.point,
        score=hit.score,
        policy_type=hit.policy_type,
        policy_code=hit.policy_code,
        policy_name=hit.policy_name,
        origin=hit.origin,
    )
