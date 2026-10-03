"""Extract and ask nodes for the case sub-agent.

``src.agents.case_graph`` owns the edges. A clarify turn reaches retrieve only
when Python accepts a retrieval request. The cite step still retrieves once
facts are locked. The planner does not name an edge.
"""

import logging

from src.features.clarify.model.assess import ClarifyPlan, assess, build_question, conflict_question
from src.features.clarify.model.catalog import OPTIONAL_FACT_KEYS, fact_lines, required_specs
from src.features.clarify.model.planner import plan_turn
from src.features.clarify.model.policy import apply_decision
from src.features.clarify.model.prompt import PROMPT_VERSION

logger = logging.getLogger(__name__)

_WORKFLOW_ACTIONS = frozenset(
    {
        "request_retrieval",
        "draft_minutes",
        "create_ticket_preview",
        "send_to_legal",
    }
)
_DIRECT_ACTIONS = frozenset({"answer_policy_question", "show_assessment", "unsupported"})


async def extract_node(state: dict) -> dict:
    """Read the narrative and merge it with facts already stored."""
    citing = state.get("step") == "cite" or bool(state.get("advance"))
    if citing or not state.get("semantic"):
        return _project(assess(state.get("text", ""), state.get("stored") or {}))
    result = await plan_turn(state)
    plan = apply_decision(
        state.get("text") or "",
        state.get("stored") or {},
        result.decision,
        fallback=result.fallback,
    )
    _log_decision(state, plan, result)
    return _project(plan)


def ask_node(state: dict) -> dict:
    """Write the one question HR still has to answer. No sanction is proposed here."""
    conflicts = list(state.get("conflicts") or [])
    if conflicts:
        return {"question": conflict_question(state.get("family", ""), conflicts)}
    question = build_question(state["family"], state.get("missing_keys", []), state.get("merged") or {})
    return {"question": question}


def route_after_extract(state: dict) -> str:
    """Choose ask, action, done, or retrieve from validated state.

    The planner may label natural-language actions, but Python keeps the edge
    decision tied to confirmed facts, dates, and the case workflow boundary.
    """
    if state.get("conflicts"):
        return "ask"
    action = state.get("requested_action") or ""
    if action in _DIRECT_ACTIONS:
        return "action"
    if not state.get("facts_locked"):
        return "ask"
    if state.get("step") == "cite" or bool(state.get("advance")):
        return "retrieve"
    ready = state.get("incident_date") is not None and state.get("agent_run_id") is not None
    if ready and (not action or action in _WORKFLOW_ACTIONS or action == "complete_facts"):
        return "retrieve"
    return "done"


def _project(plan: ClarifyPlan) -> dict:
    found = {
        "family": plan.family,
        "merged": plan.merged,
        "missing_keys": plan.missing_keys,
        "facts_locked": plan.locked,
        "conflicts": [
            {
                "key": item.key,
                "confirmed_value": item.confirmed_value,
                "proposed_value": item.proposed_value,
                "evidence": item.evidence,
            }
            for item in plan.conflicts
        ],
        "requested_action": plan.requested_action,
        "planner_fallback": plan.planner_fallback,
        "user_intent": plan.user_intent,
        "ambiguities": list(plan.ambiguities),
        "validation": plan.validation,
        "accepted_keys": list(plan.accepted_keys),
    }
    if plan.locked:
        facts = {spec.key: plan.merged[spec.key].value for spec in required_specs(plan.family)}
        for key in OPTIONAL_FACT_KEYS:
            item = plan.merged.get(key)
            if item is not None and item.confirmed and item.value:
                facts[key] = item.value
        found["facts"] = facts
        found["fact_lines"] = fact_lines(plan.family, facts)
    return found


def _log_decision(state: dict, plan: ClarifyPlan, result) -> None:
    stored = state.get("stored") or {}
    changed = []
    for key, item in plan.merged.items():
        current = stored.get(key)
        if current is None or current.value != item.value or current.confirmed != item.confirmed:
            changed.append(key)
    logger.info(
        "clarify planner version=%s model=%s latency_ms=%s family=%s confidence=%.2f keys=%s intent=%s action=%s validation=%s fallback=%s",
        PROMPT_VERSION,
        result.model,
        result.latency_ms,
        plan.family,
        result.decision.confidence,
        ",".join(sorted(changed)),
        plan.user_intent,
        plan.requested_action,
        plan.validation,
        result.reason or "none",
    )
