"""Short-term memory for case conversations.

Memory is deterministic and case-scoped: it summarizes the current working
state, pending fact keys, pending workflow action, and the last few messages.
It is context for the next turn, not evidence and not a source of sanctions.
"""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.clarify.model.assess import ClarifyPlan, StoredFact
from src.features.clarify.model.catalog import fact_label
from src.features.clarify.model.store import list_messages
from src.models.conversation_memories import ConversationMemory

RECENT_LIMIT = 8
SUMMARY_LIMIT = 1600


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
    recent = _recent_text(live_recent or (memory.recent_messages if memory is not None else []))
    if recent:
        parts.append(f"RECENT_TURNS\n{recent}")
    return "\n\n".join(parts)


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
    memory.pending_fact_keys = _pending_keys(plan)
    memory.open_questions = _open_questions(plan)
    if action_completed:
        memory.pending_action = None
    elif plan.requested_action == "draft_minutes":
        memory.pending_action = "draft_minutes"
    elif memory.pending_action != "draft_minutes":
        memory.pending_action = plan.requested_action or None
    memory.last_user_intent = plan.user_intent or None
    memory.recent_messages = await _recent_messages(session, conversation_id)
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


def _open_questions(plan: ClarifyPlan) -> list[str]:
    if plan.conflicts:
        return [f"{item.key}: chọn giữa '{item.confirmed_value}' và '{item.proposed_value}'" for item in plan.conflicts]
    if plan.missing_keys:
        return [f"{key}: {fact_label(key)}" for key in plan.missing_keys]
    if plan.locked:
        return []
    return [f"{key}: cần xác nhận" for key, item in plan.merged.items() if item.value and not item.confirmed]


def _pending_keys(plan: ClarifyPlan) -> list[str]:
    keys = list(plan.missing_keys)
    for key, item in plan.merged.items():
        if item.value and not item.confirmed and key not in keys:
            keys.append(key)
    return keys


async def _recent_messages(session: AsyncSession, conversation_id: UUID) -> list[dict[str, str]]:
    rows = (await list_messages(session, conversation_id))[-RECENT_LIMIT:]
    return [
        {
            "role": row.role,
            "content": row.content[:1000],
            "created_at": row.created_at.isoformat() if row.created_at is not None else "",
        }
        for row in rows
    ]


def _recent_text(items: object) -> str:
    lines = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = " ".join(str(item.get("content") or "").split())
        if role and content:
            lines.append(f"{role}: {content[:500]}")
    return "\n".join(lines)


def _summary(plan: ClarifyPlan, assistant_text: str) -> str:
    lines = [
        f"family={plan.family}",
        f"facts_locked={plan.locked}",
    ]
    if plan.requested_action:
        lines.append(f"requested_action={plan.requested_action}")
    if plan.user_intent:
        lines.append(f"user_intent={plan.user_intent}")
    if plan.missing_keys:
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
