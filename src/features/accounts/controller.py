"""Manager routes for HR and legal accounts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_roles
from src.core.security.rbac import RoleEnum
from src.features.accounts.model.service import create_staff, delete_staff, list_staff, update_staff
from src.features.accounts.schema import StaffAccount, StaffCreate, StaffList, StaffUpdate
from src.models.users import User

router = APIRouter(tags=["Quản lý"])


@router.get("/manager/users", response_model=StaffList)
async def get_staff(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_roles(RoleEnum.MANAGER))],
) -> StaffList:
    """Danh sách tài khoản HR và pháp chế."""
    return await list_staff(session, actor)


@router.post("/manager/users", response_model=StaffAccount, status_code=status.HTTP_201_CREATED)
async def post_staff(
    payload: StaffCreate,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_roles(RoleEnum.MANAGER))],
) -> StaffAccount:
    """Tạo tài khoản HR hoặc pháp chế."""
    return await create_staff(session, actor, payload)


@router.patch("/manager/users/{user_id}", response_model=StaffAccount)
async def patch_staff(
    user_id: UUID,
    payload: StaffUpdate,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_roles(RoleEnum.MANAGER))],
) -> StaffAccount:
    """Sửa tên, email, vai trò, mật khẩu hoặc khóa tài khoản HR hoặc pháp chế."""
    return await update_staff(session, actor, user_id, payload)


@router.delete("/manager/users/{user_id}", response_model=StaffAccount)
async def remove_staff(
    user_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_roles(RoleEnum.MANAGER))],
) -> StaffAccount:
    """Xóa tài khoản HR hoặc pháp chế. Hồ sơ đã tạo vẫn còn."""
    return await delete_staff(session, actor, user_id)
