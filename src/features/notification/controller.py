"""Notification routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.notification.model import list_notifications, mark_read
from src.features.notification.schema import NotificationList, NotificationView
from src.models.users import User

router = APIRouter(prefix="/notifications", tags=["Thông báo"])


@router.get("", response_model=NotificationList)
async def get_notifications(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.NOTIFICATION_READ))],
) -> NotificationList:
    return await list_notifications(session, actor)


@router.post("/{notification_id}/read", response_model=NotificationView)
async def post_read(
    notification_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.NOTIFICATION_READ))],
) -> NotificationView:
    return await mark_read(session, actor, notification_id)
