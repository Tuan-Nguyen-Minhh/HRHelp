"""Case status rules. Services call this instead of comparing status strings ad hoc."""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.models.cases import Case

TRANSITIONS: dict[str, frozenset[str]] = {
    "OPEN": frozenset({"NEED_INFO", "ANALYZED"}),
    "NEED_INFO": frozenset({"NEED_INFO", "ANALYZED"}),
    "ANALYZED": frozenset({"NEED_INFO", "PENDING_LEGAL", "APPROVED"}),
    "PENDING_LEGAL": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset({"DECIDED"}),
    "REJECTED": frozenset({"NEED_INFO", "ANALYZED"}),
    "DECIDED": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
}


class CaseAccessLevel(StrEnum):
    """Ranked grant stored on ``case_access``. A higher rank includes the lower ones."""

    VIEW = "VIEW"
    REVIEW = "REVIEW"
    EDIT = "EDIT"


ACCESS_RANK = {
    CaseAccessLevel.VIEW: 1,
    CaseAccessLevel.REVIEW: 2,
    CaseAccessLevel.EDIT: 3,
}


def assert_transition(current: str, target: str) -> None:
    """Reject a status change the state machine does not list."""
    allowed = TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise AppError(
            409,
            f"Không chuyển hồ sơ từ {current} sang {target}.",
            code="INVALID_CASE_TRANSITION",
            details={"from": current, "to": target},
        )


async def lock_case(session: AsyncSession, case_id: UUID) -> Case | None:
    """Lock one case row for the rest of this transaction."""
    stmt = select(Case).where(Case.id == case_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()
