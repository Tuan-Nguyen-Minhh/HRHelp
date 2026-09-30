"""Read the layered answer of a case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case
from src.common.deps import get_actor, get_session
from src.common.errors import AppError
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.answer.model.answers import load
from src.features.answer.schema import AnswerView
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Câu trả lời"])


@router.get("/{case_id}/answer", response_model=AnswerView)
async def read_answer(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
) -> AnswerView:
    """Đọc đề xuất hiện tại, đã tách bốn nhóm căn cứ."""
    case = await require_case(session, case_id, actor)
    view = await load(session, case)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có câu trả lời.")
    return view
