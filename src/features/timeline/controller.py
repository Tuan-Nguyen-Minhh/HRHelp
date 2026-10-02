"""Read-only case timeline."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.timeline.model import case_timeline
from src.features.timeline.schema import TimelineResponse
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Dòng thời gian"])


@router.get("/{case_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> TimelineResponse:
    """Ghép sự kiện đã lưu theo thời gian."""
    return await case_timeline(session, actor, case_id)
