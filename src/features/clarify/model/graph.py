"""Extract and ask nodes for the case sub-agent.

``src.agents.case_graph`` owns the edges. A clarify turn stops after ask.
Citation starts only when the turn's step is ``cite``.
"""

from src.features.clarify.model.assess import ClarifyPlan, assess, build_question
from src.features.clarify.model.catalog import fact_lines, required_specs


def extract_node(state: dict) -> dict:
    """Read the narrative and merge it with facts already stored."""
    plan: ClarifyPlan = assess(state.get("text", ""), state.get("stored") or {})
    found = {
        "family": plan.family,
        "merged": plan.merged,
        "missing_keys": plan.missing_keys,
        "facts_locked": plan.locked,
    }
    if plan.locked:
        facts = {spec.key: plan.merged[spec.key].value for spec in required_specs(plan.family)}
        found["facts"] = facts
        found["fact_lines"] = fact_lines(plan.family, facts)
    return found


def ask_node(state: dict) -> dict:
    """Write the one question HR still has to answer. No sanction is proposed here."""
    question = build_question(state["family"], state.get("missing_keys", []), state.get("merged") or {})
    return {"question": question}


def route_after_extract(state: dict) -> str:
    """Ask while a required fact is open. Cite only on the confirm step."""
    citing = state.get("step") == "cite" or bool(state.get("advance"))
    if state.get("facts_locked") and citing:
        return "retrieve"
    if state.get("facts_locked"):
        return "done"
    return "ask"
