"""Issue and refresh the session token, and open a new account."""

import hashlib
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.core.security.auth_handler import AuthHandler
from src.core.security.rbac import DEFAULT_ROLE_PERMISSIONS, RoleEnum
from src.models.permission_roles import PermissionRole
from src.models.permissions import Permission
from src.models.revoked_tokens import RevokedToken
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
    if not await _rbac_tables_available(session):
        return claims_for_role(user.role)
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
    user = await _user_by_email(session, email)
    if user is None or not user.is_active or user.deleted_at is not None:
        return None
    if not AuthHandler.verify_password(password, user.password_hash):
        return None
    return _issued(user, await load_roles_and_permissions(session, user))


async def register_account(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: str | None,
    role: str,
) -> dict[str, Any]:
    """Insert an active user, link ``user_roles`` when the role row exists, and sign in."""
    folded = email.strip().casefold()
    if await _user_by_email(session, folded) is not None:
        raise AppError(409, "Email đã được đăng ký.")
    user = User(
        email=folded,
        password_hash=AuthHandler.get_password_hash(password),
        full_name=full_name,
        role=role,
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
        if await _rbac_tables_available(session):
            role_row = await session.scalar(select(Role).where(Role.name == role))
            if role_row is not None:
                session.add(UserRole(user_id=user.id, role_id=role_row.id))
                await session.flush()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "email" not in str(getattr(exc, "orig", exc)).lower():
            raise
        raise AppError(409, "Email đã được đăng ký.") from None
    claims = await load_roles_and_permissions(session, user)
    expected = claims_for_role(role)
    if not claims["permissions"] and expected["permissions"]:
        claims = expected
    return _issued(user, claims)


async def refresh_access(session: AsyncSession, refresh_token: str) -> dict[str, Any]:
    """Issue a new access token from the roles currently stored for this user."""
    payload = AuthHandler.decode_token(refresh_token)
    if payload.get("type") != "refresh" or payload.get("user_id") is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ.")
    try:
        user_id = UUID(str(payload["user_id"]))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ.") from None
    if await _refresh_revoked(session, refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không còn hiệu lực.")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy người dùng hoặc tài khoản đã khóa.",
        )
    return _issued(user, await load_roles_and_permissions(session, user), refresh_token)


def _issued(user: User, claims: dict[str, list[str]], refresh_token: str | None = None) -> dict[str, Any]:
    """Build the login payload. A passed refresh token is kept instead of rotated."""
    data = _token_data(user)
    return {
        "access_token": AuthHandler.create_access_token(data, claims["roles"], claims["permissions"]),
        "refresh_token": refresh_token or AuthHandler.create_refresh_token(data),
        "token_type": "bearer",
        "user_id": user.id,
        "roles": claims["roles"],
    }


async def revoke_refresh(session: AsyncSession, user_id: UUID, refresh_token: str) -> None:
    """Store a hash of the refresh token so it cannot mint another access token."""
    payload = AuthHandler.decode_token(refresh_token)
    if payload.get("type") != "refresh" or str(payload.get("user_id")) != str(user_id):
        raise AppError(401, "Token không hợp lệ.", code="AUTH_REQUIRED")
    digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    existing = await session.scalar(select(RevokedToken).where(RevokedToken.token_hash == digest))
    if existing is None:
        session.add(RevokedToken(user_id=user_id, token_hash=digest))
    await session.commit()


async def _refresh_revoked(session: AsyncSession, refresh_token: str) -> bool:
    if await session.scalar(select(func.to_regclass("public.revoked_tokens"))) is None:
        return False
    digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    found = await session.scalar(select(RevokedToken.id).where(RevokedToken.token_hash == digest))
    return found is not None


async def _user_by_email(session: AsyncSession, email: str) -> User | None:
    """Match the address without regard to case. Registration stores the folded form."""
    folded = email.strip().casefold()
    if not folded:
        return None
    return await session.scalar(select(User).where(func.lower(User.email) == folded))


async def _rbac_tables_available(session: AsyncSession) -> bool:
    """Allow the legacy HR schema to authenticate until its RBAC migration runs."""
    names = ("roles", "permissions", "user_roles", "permission_roles")
    for name in names:
        if await session.scalar(select(func.to_regclass(f"public.{name}"))) is None:
            return False
    return True
