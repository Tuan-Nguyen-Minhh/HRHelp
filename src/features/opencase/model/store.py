"""Writes and reads for cases and the conversation opened with them."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.models.cases import Case
from src.models.conversations import Conversation


@dataclass(frozen=True)
class NewCase:
    """Fields required to open a case. The HTTP body is mapped before this point."""

    case_code: str
    employee_code: str
    employee_name: str
    description: str
    incident_date: date
    family: str | None = None


async def find_by_code(session: AsyncSession, case_code: str) -> Case | None:
    """Return the case that already uses this code, if any."""
    stmt = select(Case).where(Case.case_code == case_code)
    return (await session.execute(stmt)).scalar_one_or_none()


async def insert_case(session: AsyncSession, actor_id: UUID, draft: NewCase) -> Case:
    """Insert a case in status OPEN. The caller commits."""
    case = Case(
        id=uuid4(),
        case_code=draft.case_code,
        created_by=actor_id,
        employee_code=draft.employee_code,
        employee_name=draft.employee_name,
        description=draft.description,
        incident_date=draft.incident_date,
        family=draft.family,
        status="OPEN",
    )
    session.add(case)
    await session.flush()
    return case


async def insert_conversation(session: AsyncSession, actor_id: UUID, case: Case) -> Conversation:
    """Open the ACTIVE conversation that chat will append to."""
    conversation = Conversation(
        id=uuid4(),
        user_id=actor_id,
        case_id=case.id,
        title=case.case_code,
        status="ACTIVE",
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def get_active_conversation(session: AsyncSession, case_id: UUID) -> Conversation | None:
    """Return the newest ACTIVE conversation of a case."""
    stmt = (
        select(Conversation)
        .where(Conversation.case_id == case_id, Conversation.status == "ACTIVE")
        .order_by(Conversation.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
