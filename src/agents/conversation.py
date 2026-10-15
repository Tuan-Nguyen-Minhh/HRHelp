"""Conversation invariants owned by orchestration, independent of agent routes.

Agents propose results; this policy decides which parts may change durable
conversation state. Missing fields and failed steps are never deletion requests.
"""

from dataclasses import asdict, replace
from enum import StrEnum

from src.features.clarify.model.assess import ClarifyPlan
from src.features.clarify.model.catalog import FactSpec, default_dynamic_specs, safe_dynamic_key

WORKFLOW_ACTIONS = frozenset({"draft_minutes", "create_ticket_preview", "send_to_legal", "request_retrieval"})
FACT_INTENTS = frozenset({"provide_facts", "confirm_facts", "correct_facts", "continue"})
NEUTRAL_ACTIONS = frozenset({"", "need_clarification", "complete_facts", "request_retrieval"})
RECENT_CONTEXT_BUDGET = 12000


class StateUpdate(StrEnum):
    PRESERVE = "preserve"
    PROGRESS = "progress"


class TaskChange(StrEnum):
    KEEP = "keep"
    REPLACE = "replace"
    CANCEL = "cancel"


ORCHESTRATOR_RULES = """SHARED CONVERSATION CONTRACT
- The latest user message determines the current intent. History provides context, not new commands.
- A reply answering outstanding questions continues the active task; the user need not repeat its command.
- Supplying negative values or mentioning laws/contract clauses as facts does not itself ask a policy question.
- A side question does not cancel or replace the active task or its outstanding fact requirements.
- Replace or cancel a task only on an explicit user request. Never infer cancellation from missing output fields.
- Preserve the active fact schema, including labels, questions and required flags, while collecting its answers.
- Extract only supported data. A pending task never authorizes inventing values or bypassing validation.
- A processing/schema/transport failure is not evidence that the user's intent is unclear.
"""


def snapshot_plan(state: dict) -> ClarifyPlan:
    """Project validated state without interpreting history as a fresh request."""
    stored = dict(state.get("stored") or {})
    family = state.get("family") or "GENERAL"
    specs = tuple(state.get("active_specs") or default_dynamic_specs(family, set(stored)))
    required = [spec for spec in specs if spec.required]
    missing = [spec.key for spec in required if spec.key not in stored or not stored[spec.key].value.strip()]
    return ClarifyPlan(
        family=family,
        merged=stored,
        missing_keys=missing,
        locked=not missing and all(stored[spec.key].confirmed for spec in required),
        specs=specs,
        state_update=StateUpdate.PRESERVE.value,
    )


def reconcile_plan(plan: ClarifyPlan, state: dict) -> ClarifyPlan:
    """Resume any registered workflow only after the turn has been validated."""
    explicit = state.get("requested_action") or ""
    pending = state.get("pending_action") or ""
    action = plan.requested_action
    if explicit in WORKFLOW_ACTIONS:
        action = explicit
    elif (
        pending in WORKFLOW_ACTIONS
        and action in NEUTRAL_ACTIONS | {pending}
        and (plan.user_intent in FACT_INTENTS or plan.accepted_keys or not state.get("semantic"))
        and (not plan.planner_fallback or plan.accepted_keys)
    ):
        action = pending
    effect = StateUpdate.PROGRESS
    if not plan.accepted_keys and (
        plan.planner_fallback or (plan.user_intent not in FACT_INTENTS and action not in WORKFLOW_ACTIONS)
    ):
        effect = StateUpdate.PRESERVE
    return replace(
        plan,
        requested_action=action,
        state_update=effect.value,
        task_change=state.get("task_change") or TaskChange.KEEP.value,
    )


def memory_patch(plan: ClarifyPlan, *, pending_action: str | None = None, action_completed: bool = False) -> dict:
    """Return an explicit patch; an unrelated/failed route cannot clear progress."""
    patch = {}
    if plan.state_update == StateUpdate.PROGRESS:
        pending = list(plan.missing_keys)
        for key, item in plan.merged.items():
            if item.value and not item.confirmed and key not in pending:
                pending.append(key)
        questions = [
            f"{item.key}: chọn giữa '{item.confirmed_value}' và '{item.proposed_value}'" for item in plan.conflicts
        ]
        if not questions:
            labels = {spec.key: spec.label for spec in plan.specs}
            questions = [f"{key}: {labels.get(key, key)}" for key in pending]
        patch.update(
            pending_fact_keys=pending,
            open_questions=questions,
            working_state={"version": 1, "family": plan.family, "specs": [asdict(spec) for spec in plan.specs]},
        )
        if plan.user_intent:
            patch["last_user_intent"] = plan.user_intent
        if plan.requested_action in WORKFLOW_ACTIONS and (
            not pending_action or pending_action == plan.requested_action or plan.task_change == TaskChange.REPLACE
        ):
            patch["pending_action"] = plan.requested_action
    if plan.task_change == TaskChange.CANCEL:
        patch.update(pending_action=None, pending_fact_keys=[], open_questions=[])
    elif action_completed and (
        not pending_action or pending_action == plan.requested_action or plan.task_change == TaskChange.REPLACE
    ):
        patch["pending_action"] = None
    return patch


def working_specs(value: object) -> tuple[FactSpec, ...]:
    """Read the durable schema; old conversations without it remain supported."""
    if not isinstance(value, dict):
        return ()
    result = []
    items = value.get("specs")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not safe_dynamic_key(str(item.get("key") or "")):
            continue
        result.append(
            FactSpec(
                key=item["key"],
                label=str(item.get("label") or item["key"]),
                question=str(item.get("question") or item["key"]),
                required=item.get("required", True) is True,
                source=str(item.get("source") or "memory"),
            )
        )
    return tuple(result)


def recent_turns(items: object, *, budget: int = RECENT_CONTEXT_BUDGET) -> str:
    """Keep complete recent messages. Never cut the tail of a user's answer.

    The latest message is included even when it exceeds the soft budget. Older
    messages are omitted as whole units; durable facts/schema live separately.
    """
    lines = []
    size = 0
    for item in reversed(items if isinstance(items, list) else []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role not in {"USER", "ASSISTANT"} or not content:
            continue
        line = f"{role}: {content}"
        if lines and size + len(line) > budget:
            break
        lines.append(line)
        size += len(line) + 1
    return "\n".join(reversed(lines))
