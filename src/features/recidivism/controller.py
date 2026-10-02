"""HR asks for prior sanctions. The result is not confirmed until HR says so."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.recidivism.model import inspect_recidivism
from src.features.recidivism.schema import RecidivismView
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Tái phạm"])


@router.post("/{case_id}/recidivism", response_model=RecidivismView)
async def post_recidivism(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CONFIRM))],
) -> RecidivismView:
    """Đếm quyết định cũ cùng nhân viên và cùng loại vi phạm. Không dùng embedding."""
    return await inspect_recidivism(session, actor, case_id)
