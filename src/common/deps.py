"""FastAPI dependencies for the request session and the acting user."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.common.errors import AppError
from src.db.session import SessionLocal
from src.models.users import User


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session. The feature service commits or rolls it back."""
    async with SessionLocal() as session:
        yield session


async def get_actor(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[UUID, Header(alias="X-User-Id", description="Id người dùng đang thao tác")],
) -> User:
    """Load the active user named by ``X-User-Id``.

    Login is a separate feature. Until it exists, the client sends the user id.
    """
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "Không tìm thấy người dùng hoặc tài khoản đã khóa.")
    return user
