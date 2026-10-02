"""Write an in-app notification in the caller's transaction."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.case_access import CaseAccess
from src.models.notifications import Notification
from src.models.users import User


async def notify(
    session: AsyncSession,
    *,
    user_id: UUID,
    event: str,
    title: str,
    body: str,
    case_id: UUID | None = None,
) -> Notification:
    """Insert one notice. The caller commits."""
    row = Notification(user_id=user_id, case_id=case_id, event=event, title=title, body=body)
    session.add(row)
    await session.flush()
    return row


async def notify_reviewers(
    session: AsyncSession,
    *,
    case_id: UUID,
    event: str,
    title: str,
    body: str,
) -> None:
    """Notify every user who was granted REVIEW on this case."""
    stmt = select(CaseAccess.user_id).where(CaseAccess.case_id == case_id, CaseAccess.access_level == "REVIEW")
    user_ids = list((await session.scalars(stmt)).all())
    for user_id in user_ids:
        await notify(session, user_id=user_id, event=event, title=title, body=body, case_id=case_id)


async def notify_managers(
    session: AsyncSession,
    *,
    case_id: UUID,
    event: str,
    title: str,
    body: str,
) -> None:
    """Notify every active manager. The final queue is by role, not by a case grant."""
    await _notify_role(session, role="MANAGER", case_id=case_id, event=event, title=title, body=body)


async def notify_legal(
    session: AsyncSession,
    *,
    case_id: UUID,
    event: str,
    title: str,
    body: str,
) -> None:
    """Notify every active legal officer. The legal page lists tickets by role."""
    await _notify_role(session, role="LEGAL", case_id=case_id, event=event, title=title, body=body)


async def _notify_role(
    session: AsyncSession,
    *,
    role: str,
    case_id: UUID,
    event: str,
    title: str,
    body: str,
) -> None:
    stmt = select(User.id).where(User.role == role, User.is_active.is_(True), User.deleted_at.is_(None))
    for user_id in (await session.scalars(stmt)).all():
        await notify(session, user_id=user_id, event=event, title=title, body=body, case_id=case_id)
