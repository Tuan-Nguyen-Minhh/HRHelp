"""Copy RoleEnum and PermissionEnum into the database. Safe to run again."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.rbac import DEFAULT_ROLE_PERMISSIONS, PermissionEnum, RoleEnum
from src.models.permission_roles import PermissionRole
from src.models.permissions import Permission
from src.models.roles import Role
from src.models.user_roles import UserRole
from src.models.users import User


async def seed_rbac(session: AsyncSession) -> None:
    """Insert missing roles, permissions, links, and one user_roles row per user."""
    await _seed_permissions(session)
    await _seed_roles(session)
    await _seed_role_permissions(session)
    await _seed_user_roles(session)
    await session.commit()
    print("[RBAC] Seed completed.")


async def _seed_permissions(session: AsyncSession) -> None:
    for item in PermissionEnum:
        found = await session.scalar(select(Permission).where(Permission.name == item.value))
        if found is None:
            resource, _, action = item.value.partition(":")
            session.add(Permission(name=item.value, resource=resource, action=action))
    await session.flush()


async def _seed_roles(session: AsyncSession) -> None:
    for item in RoleEnum:
        found = await session.scalar(select(Role).where(Role.name == item.value))
        if found is None:
            session.add(Role(name=item.value))
    await session.flush()


async def _seed_role_permissions(session: AsyncSession) -> None:
    for role_name, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = await session.scalar(select(Role).where(Role.name == role_name.value))
        if role is None:
            continue
        for permission_name in permission_names:
            permission = await session.scalar(select(Permission).where(Permission.name == permission_name))
            if permission is None:
                continue
            link = await session.scalar(
                select(PermissionRole).where(
                    PermissionRole.role_id == role.id,
                    PermissionRole.permission_id == permission.id,
                )
            )
            if link is None:
                session.add(PermissionRole(role_id=role.id, permission_id=permission.id))
    await session.flush()


async def _seed_user_roles(session: AsyncSession) -> None:
    """Mirror ``users.role`` until a user is assigned through ``user_roles``."""
    users = (await session.scalars(select(User))).all()
    for user in users:
        role = await session.scalar(select(Role).where(Role.name == user.role))
        if role is None:
            continue
        link = await session.scalar(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id))
        if link is None:
            session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()
