"""Messages and facts of one case. Agent runs live in ``src.agents``."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.clock import utc_now
from src.models.case_facts import CaseFact
from src.models.messages import Message


@dataclass(frozen=True)
class NewMessage:
    """A row for ``messages``."""

    conversation_id: UUID
    role: str
    content: str
    metadata: dict | None = None


@dataclass(frozen=True)
class FactWrite:
    """The confirmed or still-open value of one fact."""

    case_id: UUID
    key: str
    value: str
    confirmed: bool
    actor_id: UUID | None
    source_message_id: UUID | None = None


async def add_message(session: AsyncSession, draft: NewMessage) -> Message:
    """Insert a message and flush so later rows can point at it."""
    message = Message(
        id=uuid4(),
        conversation_id=draft.conversation_id,
        role=draft.role,
        content=draft.content,
        message_metadata=draft.metadata,
    )
    session.add(message)
    await session.flush()
    return message


async def list_user_text(session: AsyncSession, conversation_id: UUID) -> str:
    """Concatenate user messages in the order they were sent."""
    stmt = (
        select(Message.content)
        .where(Message.conversation_id == conversation_id, Message.role == "USER")
        .order_by(Message.created_at.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return "\n".join(rows)


async def list_fact_rows(session: AsyncSession, case_id: UUID) -> list[CaseFact]:
    """Return every fact stored on the case."""
    stmt = select(CaseFact).where(CaseFact.case_id == case_id)
    return list((await session.execute(stmt)).scalars().all())


async def write_fact(session: AsyncSession, draft: FactWrite) -> CaseFact:
    """Insert or update one fact. Confirmation columns stay paired."""
    row = await _find_fact(session, draft.case_id, draft.key)
    if row is None:
        row = CaseFact(id=uuid4(), case_id=draft.case_id, fact_key=draft.key, source_message_id=draft.source_message_id)
        session.add(row)
    row.fact_value = draft.value
    if draft.source_message_id is not None:
        row.source_message_id = draft.source_message_id
    row.confirmed = draft.confirmed
    row.confirmed_by = draft.actor_id if draft.confirmed else None
    row.confirmed_at = utc_now() if draft.confirmed else None
    await session.flush()
    return row


async def save_extracted(session: AsyncSession, draft: FactWrite) -> None:
    """Store an unconfirmed extraction. A confirmed fact is not overwritten."""
    row = await _find_fact(session, draft.case_id, draft.key)
    if row is not None and row.confirmed:
        return
    if row is not None and row.fact_value == draft.value:
        return
    await write_fact(session, draft)


async def _find_fact(session: AsyncSession, case_id: UUID, key: str) -> CaseFact | None:
    stmt = select(CaseFact).where(CaseFact.case_id == case_id, CaseFact.fact_key == key)
    return (await session.execute(stmt)).scalar_one_or_none()
