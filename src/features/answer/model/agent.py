"""Scaffold for the sanction agent. The case sub-agent does not call this graph.

Feature 6 reads ``CaseHandoff`` and is owned by another developer. Wire
``build_recommend_agent`` only when that agent is ready to join the system.
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.handoff import CaseHandoff, CitedPassage
from src.features.answer.model.draft import AnswerDraft, AnswerInput, draft_answer
from src.features.answer.model.layers import LayeredBasis, split_passages
from src.features.cite.model.passage import Passage


class RecommendState(TypedDict, total=False):
    """Input is only ``handoff``. The supervisor reads the other three keys."""

    handoff: CaseHandoff
    precedent_note: str
    layered: LayeredBasis
    draft: AnswerDraft


def build_recommend_agent() -> CompiledStateGraph:
    """Compile precedent → recommend for one handoff message."""
    graph = StateGraph(RecommendState)
    graph.add_node("precedent", precedent_node)
    graph.add_node("recommend", recommend_node)
    graph.set_entry_point("precedent")
    graph.add_edge("precedent", "recommend")
    graph.add_edge("recommend", END)
    return graph.compile()


def precedent_node(state: dict) -> dict:
    """Count precedent passages on the handoff. They do not raise the sanction."""
    count = sum(1 for item in _message(state).passages if item.policy_type == "PRECEDENT")
    if count == 0:
        note = "Không có đoạn tiền lệ trong lượt đối chiếu này."
    else:
        note = f"Có {count} đoạn tiền lệ. Tiền lệ chỉ để đối chiếu, không tự nâng mức kỷ luật."
    return {"precedent_note": note}


def recommend_node(state: dict) -> dict:
    """Layer the cited passages, then draft sanction, process, and risk."""
    message = _message(state)
    layered = split_passages([_passage(item) for item in message.passages])
    draft = draft_answer(
        AnswerInput(
            family=message.family,
            facts=dict(message.facts),
            fact_lines=list(message.fact_lines),
            employee_name=message.employee_name,
            incident_date=message.incident_date,
            layered=layered,
            precedent_note=state.get("precedent_note", ""),
        )
    )
    return {"layered": layered, "draft": draft}


def _message(state: dict) -> CaseHandoff:
    message = state.get("handoff")
    if not isinstance(message, CaseHandoff):
        raise TypeError("Sanction agent expects state['handoff'] to be a CaseHandoff.")
    return message


def _passage(item: CitedPassage) -> Passage:
    return Passage(
        chunk_id=item.chunk_id,
        policy_version_id=item.policy_version_id,
        content=item.content,
        article=item.article,
        clause=item.clause,
        point=item.point,
        score=item.score,
        policy_type=item.policy_type,
        policy_code=item.policy_code,
        policy_name=item.policy_name,
    )
