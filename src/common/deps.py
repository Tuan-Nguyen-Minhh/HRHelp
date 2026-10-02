"""FastAPI dependencies for the request session and the acting user."""

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.errors import AppError
from src.core.security.dependencies import get_current_active_user
from src.db.session import SessionLocal
from src.models.users import User


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session. The feature service commits. A raised error rolls back."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_actor(
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[dict[str, Any], Depends(get_current_active_user)],
) -> User:
    """Load the active user named by the access token.

    The token already carried the permission check. This read exists so the
    feature can store ``users.id`` on the case.
    """
    try:
        user_id = UUID(str(current["user_id"]))
    except ValueError:
        raise AppError(401, "Không tìm thấy người dùng hoặc tài khoản đã khóa.") from None
    user = await session.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise AppError(401, "Không tìm thấy người dùng hoặc tài khoản đã khóa.")
    return user
