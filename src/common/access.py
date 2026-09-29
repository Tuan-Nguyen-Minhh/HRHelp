"""Who may open a case and who may keep editing it."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.errors import AppError
from src.models.cases import Case
from src.models.users import User

OPEN_ROLES = frozenset({"HR", "MANAGER"})
MUTABLE_STATUSES = frozenset({"OPEN", "NEED_INFO", "ANALYZED", "REJECTED"})


def require_case_role(actor: User) -> None:
    """HR and managers open cases and chat. Legal reviews a different feature."""
    if actor.role not in OPEN_ROLES:
        raise AppError(403, "Chỉ HR hoặc quản lý được mở hồ sơ và chat.")


async def require_case(session: AsyncSession, case_id: UUID, actor: User) -> Case:
    """Return the case when the actor is the person who created it."""
    require_case_role(actor)
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.")
    if case.created_by != actor.id:
        raise AppError(403, "Chỉ người tạo hồ sơ được xem và sửa vụ này.")
    return case


async def require_mutable_case(session: AsyncSession, case_id: UUID, actor: User) -> Case:
    """Return a case that can still accept facts or a new answer."""
    case = await require_case(session, case_id, actor)
    if case.status not in MUTABLE_STATUSES:
        raise AppError(409, f"Hồ sơ đang ở {case.status}, không nhận thêm tình tiết.")
    return case
