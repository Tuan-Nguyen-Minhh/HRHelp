"""Read the acting user from the access token.

Roles and permissions stay in the token. This module does not query the database.
"""

from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.core.security.auth_handler import AuthHandler
from src.core.security.oauth2_scheme import oauth2_scheme

_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Không xác thực được phiên đăng nhập.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Decode an access token into the claims the guards read."""
    if not token:
        raise _CREDENTIALS
    payload = AuthHandler.decode_token(token)
    if payload.get("type") != "access":
        raise _CREDENTIALS
    user_id = payload.get("user_id")
    if user_id is None:
        raise _CREDENTIALS
    try:
        UUID(str(user_id))
    except ValueError:
        raise _CREDENTIALS from None
    return {
        "user_id": str(user_id),
        "email": payload.get("email"),
        "roles": list(payload.get("roles") or []),
        "permissions": list(payload.get("permissions") or []),
        "is_active": bool(payload.get("is_active", True)),
    }


async def get_current_active_user(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject a token that was issued for a locked account."""
    if not current_user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản đã khóa.")
    return current_user
