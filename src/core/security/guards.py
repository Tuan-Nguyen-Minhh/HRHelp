"""Route guards.

FastAPI only sees ``Depends`` placed on the route, so each guard returns a
dependency instead of wrapping the endpoint.
"""

from typing import Any

from fastapi import Depends, HTTPException, status

from src.core.security.dependencies import get_current_active_user
from src.core.security.rbac import PermissionEnum, RoleEnum


def _check_permissions(current_user: dict[str, Any], permissions: tuple[PermissionEnum, ...]) -> None:
    held = set(current_user.get("permissions") or [])
    missing = [item.value for item in permissions if item.value not in held]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Thiếu quyền: {', '.join(missing)}.",
        )


def _check_roles(current_user: dict[str, Any], roles: tuple[RoleEnum, ...]) -> None:
    held = set(current_user.get("roles") or [])
    if not any(item.value in held for item in roles):
        allowed = ", ".join(item.value for item in roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cần một trong các vai trò: {allowed}.",
        )


def require_permissions(*permissions: PermissionEnum):
    """Demand every named permission from the access token."""

    async def dependency(
        current_user: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        _check_permissions(current_user, permissions)
        return current_user

    return dependency


def require_roles(*roles: RoleEnum):
    """Demand at least one of the named roles from the access token."""

    async def dependency(
        current_user: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        _check_roles(current_user, roles)
        return current_user

    return dependency


def require_roles_and_permissions(
    *roles: RoleEnum,
    permissions: tuple[PermissionEnum, ...] = (),
):
    """Demand a role and, when given, every permission."""

    async def dependency(
        current_user: dict[str, Any] = Depends(get_current_active_user),
    ) -> dict[str, Any]:
        _check_roles(current_user, roles)
        if permissions:
            _check_permissions(current_user, permissions)
        return current_user

    return dependency
