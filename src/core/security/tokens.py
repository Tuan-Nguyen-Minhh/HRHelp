"""Issue and refresh the session token."""

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.auth_handler import AuthHandler
from src.core.security.rbac import DEFAULT_ROLE_PERMISSIONS, RoleEnum
from src.models.permission_roles import PermissionRole
from src.models.permissions import Permission
from src.models.roles import Role
from src.models.user_roles import UserRole
from src.models.users import User


def claims_for_role(role: str) -> dict[str, list[str]]:
    """Permissions of a role that has no ``user_roles`` row yet."""
    try:
        permissions = list(DEFAULT_ROLE_PERMISSIONS[RoleEnum(role)])
    except ValueError:
        permissions = []
    return {"roles": [role], "permissions": permissions}


async def load_roles_and_permissions(session: AsyncSession, user: User) -> dict[str, list[str]]:
    """Read the user's roles and the permissions those roles hold."""
    role_names = list(
        (
            await session.scalars(
                select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
            )
        ).all()
    )
    if not role_names:
        return claims_for_role(user.role)
    permission_names = list(
        (
            await session.scalars(
                select(Permission.name)
                .join(PermissionRole, PermissionRole.permission_id == Permission.id)
                .join(UserRole, UserRole.role_id == PermissionRole.role_id)
                .where(UserRole.user_id == user.id)
                .distinct()
            )
        ).all()
    )
    return {"roles": role_names, "permissions": permission_names}


def _token_data(user: User) -> dict[str, Any]:
    return {"user_id": str(user.id), "email": user.email, "is_active": bool(user.is_active)}


async def authenticate(session: AsyncSession, email: str, password: str) -> dict[str, Any] | None:
    """Return a token pair, or None when the email, password, or account is rejected."""
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None
    if not AuthHandler.verify_password(password, user.password_hash):
        return None
    claims = await load_roles_and_permissions(session, user)
    data = _token_data(user)
    return {
        "access_token": AuthHandler.create_access_token(data, claims["roles"], claims["permissions"]),
        "refresh_token": AuthHandler.create_refresh_token(data),
        "token_type": "bearer",
        "user_id": user.id,
        "roles": claims["roles"],
    }


async def refresh_access(session: AsyncSession, refresh_token: str) -> dict[str, Any]:
    """Issue a new access token from the roles currently stored for this user."""
    payload = AuthHandler.decode_token(refresh_token)
    if payload.get("type") != "refresh" or payload.get("user_id") is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ.")
    try:
        user_id = UUID(str(payload["user_id"]))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ.") from None
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy người dùng hoặc tài khoản đã khóa.",
        )
    claims = await load_roles_and_permissions(session, user)
    data = _token_data(user)
    return {
        "access_token": AuthHandler.create_access_token(data, claims["roles"], claims["permissions"]),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "roles": claims["roles"],
    }
