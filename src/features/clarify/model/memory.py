"""Authoritative working-state projection and raw short-term conversation memory.

Memory is deterministic and case-scoped: it summarizes the current working
state, pending fact keys, pending workflow action, and the last few messages.
It is context for the next turn, not evidence and not a source of sanctions.
``dialogue_context`` separately interprets turn relationships before graph execution;
its model-derived checkpoints live in message metadata, never working facts/tasks.
"""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.conversation import StateUpdate, TaskChange, memory_patch, recent_turns
from src.features.clarify.model.assess import ClarifyPlan, StoredFact
from src.features.clarify.model.catalog import fact_label
from src.features.clarify.model.store import list_messages
from src.models.conversation_memories import ConversationMemory

RECENT_LIMIT = 8
SUMMARY_LIMIT = 1600
SIDE_SCOPES = frozenset({"general", "system_help", "routing_clarification", "routing_error"})


def is_business_message(row) -> bool:
    meta = getattr(row, "message_metadata", None) or {}
    return not meta.get("internal") and meta.get("context_scope") not in SIDE_SCOPES


async def side_context(session: AsyncSession, conversation_id: UUID) -> dict:
    """Separate dialogue state; never merge this object into case facts or summary."""
    rows = await list_messages(session, conversation_id)
    general = []
    help_messages = []
    last_assistant = None
    for row in rows:
        meta = getattr(row, "message_metadata", None) or {}
        if meta.get("internal") or row.role not in {"USER", "ASSISTANT"}:
            continue
        if row.role == "ASSISTANT":
            last_assistant = row
        if meta.get("context_scope") == "general" and meta.get("include_in_general_context"):
            general.append({"role": row.role, "content": row.content})
        if meta.get("context_scope") == "system_help" or meta.get("kind") == "system_help":
            help_messages.append({"role": row.role, "content": row.content})
    result = {"general_messages": general[-RECENT_LIMIT:], "help_messages": help_messages[-RECENT_LIMIT:]}
    if last_assistant is not None:
        meta = getattr(last_assistant, "message_metadata", None) or {}
        result["last_reply_kind"] = meta.get("kind") or "business"
        if meta.get("routing_clarification"):
            result["routing_clarification"] = meta["routing_clarification"]
        if meta.get("help_topic_ids"):
            result["last_help_topics"] = meta["help_topic_ids"]
    return result


async def build_turn_context(
    session: AsyncSession,
    conversation_id: UUID | None,
    case_description: str,
    stored: dict[str, StoredFact],
    *,
    case_code: str | None = None,
    employee_code: str | None = None,
    employee_name: str | None = None,
    incident_date: object | None = None,
) -> str:
    """Return compact context for the planner instead of a raw full transcript."""
    memory = await get_memory(session, conversation_id) if conversation_id else None
    live_recent = await _recent_messages(session, conversation_id) if conversation_id else []
    parts = []
    profile = _case_profile(
        case_code=case_code,
        employee_code=employee_code,
        employee_name=employee_name,
        incident_date=incident_date,
    )
    if profile:
        parts.append("CASE PROFILE\n" + profile)
    if case_description:
        parts.append(f"CASE DESCRIPTION\n{case_description}")
    if stored:
        parts.append("WORKING FACTS\n" + "\n".join(_fact_line(key, value) for key, value in sorted(stored.items())))
    if memory is not None:
        if memory.summary:
            parts.append(f"SHORT_TERM_MEMORY\n{memory.summary}")
        pending = _strings(memory.pending_fact_keys)
        if pending:
            labels = ", ".join(f"{key} ({fact_label(key)})" for key in pending)
            parts.append(f"PENDING_FACT_KEYS\n{labels}")
        if memory.pending_action:
            parts.append(f"PENDING_ACTION\n{memory.pending_action}")
        if memory.last_user_intent:
            parts.append(f"LAST_USER_INTENT\n{memory.last_user_intent}")
    recent = recent_turns(live_recent or (memory.recent_messages if memory is not None else []))
    if recent:
        parts.append(f"RECENT_TURNS\n{recent}")
    return "\n\n".join(parts)


async def user_fact_sources(session: AsyncSession, conversation_id: UUID) -> list[str]:
    """Original recent business USER turns for evidence checks, never assistant prose."""
    return [row["content"] for row in await _recent_messages(session, conversation_id) if row["role"] == "USER"]


async def update_memory(
    session: AsyncSession,
    conversation_id: UUID,
    plan: ClarifyPlan,
    assistant_text: str,
    *,
    action_completed: bool = False,
) -> None:
    """Persist the current turn memory. The caller owns commit/rollback."""
    memory = await ensure_memory(session, conversation_id)
    if memory is None:
        return
    for key, value in memory_patch(
        plan, pending_action=memory.pending_action, action_completed=action_completed
    ).items():
        setattr(memory, key, value)
    memory.recent_messages = await _recent_messages(session, conversation_id)
    if plan.state_update == StateUpdate.PROGRESS or plan.task_change == TaskChange.CANCEL:
        memory.summary = _summary(plan, assistant_text)
    await session.flush()


async def get_memory(session: AsyncSession, conversation_id: UUID | None) -> ConversationMemory | None:
    if conversation_id is None:
        return None
    if not await _memory_table_exists(session):
        return None
    stmt = select(ConversationMemory).where(ConversationMemory.conversation_id == conversation_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def ensure_memory(session: AsyncSession, conversation_id: UUID) -> ConversationMemory | None:
    if not await _memory_table_exists(session):
        return None
    row = await get_memory(session, conversation_id)
    if row is not None:
        return row
    row = ConversationMemory(conversation_id=conversation_id)
    session.add(row)
    await session.flush()
    return row


def _fact_line(key: str, item: StoredFact) -> str:
    status = "confirmed" if item.confirmed else "pending"
    return f"- {key} ({fact_label(key)}): {item.value} [{status}]"


def _case_profile(
    *,
    case_code: str | None,
    employee_code: str | None,
    employee_name: str | None,
    incident_date: object | None,
) -> str:
    lines = []
    if case_code:
        lines.append(f"- case_code: {case_code}")
    if employee_name:
        lines.append(f"- employee_name: {employee_name}")
    if employee_code:
        lines.append(f"- employee_code: {employee_code}")
    isoformat = getattr(incident_date, "isoformat", None)
    if callable(isoformat):
        lines.append(f"- incident_date: {isoformat()}")
    elif incident_date:
        lines.append(f"- incident_date: {incident_date}")
    return "\n".join(lines)


async def _recent_messages(session: AsyncSession, conversation_id: UUID) -> list[dict[str, str]]:
    rows = [
        row
        for row in await list_messages(session, conversation_id)
        if row.role in {"USER", "ASSISTANT"} and is_business_message(row)
    ][-RECENT_LIMIT:]
    return [
        {
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat() if row.created_at is not None else "",
        }
        for row in rows
    ]


def _summary(plan: ClarifyPlan, assistant_text: str) -> str:
    lines = [
        f"family={plan.family}",
        f"facts_locked={plan.locked}",
    ]
    if plan.requested_action and plan.task_change != TaskChange.CANCEL:
        lines.append(f"requested_action={plan.requested_action}")
    if plan.user_intent:
        lines.append(f"user_intent={plan.user_intent}")
    if plan.missing_keys and plan.task_change != TaskChange.CANCEL:
        lines.append("missing=" + ", ".join(f"{key} ({fact_label(key)})" for key in plan.missing_keys))
    if plan.merged:
        values = []
        for key, item in sorted(plan.merged.items()):
            mark = "confirmed" if item.confirmed else "pending"
            values.append(f"{key}={item.value} [{mark}]")
        lines.append("facts=" + "; ".join(values))
    if assistant_text:
        lines.append("last_assistant=" + " ".join(assistant_text.split())[:500])
    return "\n".join(lines)[:SUMMARY_LIMIT]


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


async def _memory_table_exists(session: AsyncSession) -> bool:
    found = await session.scalar(text("select to_regclass('public.conversation_memories')"))
    return found is not None
