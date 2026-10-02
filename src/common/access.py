"""Who may open a case and who may read or edit it."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.errors import AppError
from src.common.workflow import ACCESS_RANK, CaseAccessLevel
from src.models.case_access import CaseAccess
from src.models.cases import Case
from src.models.users import User

OPEN_ROLES = frozenset({"HR", "MANAGER"})
MUTABLE_STATUSES = frozenset({"OPEN", "NEED_INFO", "ANALYZED", "REJECTED"})


def require_case_role(actor: User) -> None:
    """HR and managers open cases and chat. Legal reviews a different feature."""
    if actor.role not in OPEN_ROLES:
        raise AppError(403, "Chỉ HR hoặc quản lý được mở hồ sơ và chat.", code="FORBIDDEN")


async def require_case_access(
    session: AsyncSession,
    user: User,
    case: Case,
    level: CaseAccessLevel = CaseAccessLevel.VIEW,
) -> None:
    """Allow the creator, an admin, or a grant that meets ``level``.

    The creator of a case has full access. A grant of EDIT includes REVIEW
    and VIEW. REVIEW includes VIEW. Routers must not reimplement this check.
    """
    if user.role == "ADMIN":
        return
    if case.created_by == user.id and user.role in OPEN_ROLES:
        return
    row = await session.scalar(
        select(CaseAccess).where(CaseAccess.case_id == case.id, CaseAccess.user_id == user.id)
    )
    held = ACCESS_RANK.get(CaseAccessLevel(row.access_level), 0) if row is not None else 0
    if held < ACCESS_RANK[level]:
        raise AppError(403, "Bạn không có quyền trên hồ sơ này.", code="FORBIDDEN")


async def require_case(session: AsyncSession, case_id: UUID, actor: User) -> Case:
    """Return the case when the actor may view it."""
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    await require_case_access(session, actor, case, CaseAccessLevel.VIEW)
    return case


async def require_mutable_case(session: AsyncSession, case_id: UUID, actor: User) -> Case:
    """Return a case that HR or a manager with edit access can still change."""
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role not in OPEN_ROLES:
        raise AppError(403, "Chỉ HR hoặc quản lý được sửa hồ sơ.", code="FORBIDDEN")
    await require_case_access(session, actor, case, CaseAccessLevel.EDIT)
    if case.status not in MUTABLE_STATUSES:
        raise AppError(
            409,
            f"Hồ sơ đang ở {case.status}, không nhận thêm tình tiết.",
            code="CASE_NOT_EDITABLE",
        )
    return case


async def visible_case_ids(session: AsyncSession, actor: User) -> set[UUID] | None:
    """Cases this user may aggregate. ``None`` means every case, for an admin."""
    if actor.role == "ADMIN":
        return None
    created = select(Case.id).where(Case.created_by == actor.id)
    granted = select(CaseAccess.case_id).where(CaseAccess.user_id == actor.id)
    rows = (await session.scalars(created.union(granted))).all()
    return set(rows)


def case_visibility(actor: User):
    """SQL filter for list and dashboard queries. Admin is unrestricted."""
    if actor.role == "ADMIN":
        return None
    grant = select(CaseAccess.case_id).where(CaseAccess.user_id == actor.id)
    return or_(Case.created_by == actor.id, Case.id.in_(grant))
