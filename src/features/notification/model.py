"""Read and mark the caller's notices. One user cannot read another's."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.clock import utc_now
from src.common.errors import AppError
from src.features.notification.schema import NotificationList, NotificationView
from src.models.notifications import Notification
from src.models.users import User


async def list_notifications(session: AsyncSession, actor: User) -> NotificationList:
    rows = list(
        (
            await session.scalars(
                select(Notification)
                .where(Notification.user_id == actor.id)
                .order_by(Notification.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    return NotificationList(notifications=[_view(row) for row in rows])


async def mark_read(session: AsyncSession, actor: User, notification_id: UUID) -> NotificationView:
    row = await session.get(Notification, notification_id)
    if row is None or row.user_id != actor.id:
        raise AppError(404, "Không tìm thấy thông báo.", code="NOT_FOUND")
    if row.read_at is None:
        row.read_at = utc_now()
        await session.commit()
    return _view(row)


def _view(row: Notification) -> NotificationView:
    return NotificationView(
        id=row.id,
        case_id=row.case_id,
        event=row.event,
        title=row.title,
        body=row.body,
        read_at=row.read_at,
        created_at=row.created_at,
    )
