"""Token claims and route guards. No database."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from src.core.config import settings
from src.core.security.auth_handler import AuthHandler
from src.core.security.dependencies import get_current_user
from src.core.security.guards import require_permissions, require_roles
from src.core.security.rbac import PermissionEnum, RoleEnum
from src.core.security.tokens import claims_for_role


def test_access_token_carries_roles_and_permissions():
    token = AuthHandler.create_access_token(
        {"user_id": "6f0b4c3e-1a2b-4c5d-8e9f-001122334455", "email": "hr@vinuni.edu.vn", "is_active": True},
        roles=["HR"],
        permissions=["case:open", "case:chat"],
    )
    payload = AuthHandler.decode_token(token)
    assert payload["type"] == "access"
    assert payload["roles"] == ["HR"]
    assert payload["permissions"] == ["case:open", "case:chat"]


def test_refresh_token_is_not_an_access_token():
    token = AuthHandler.create_refresh_token({"user_id": "6f0b4c3e-1a2b-4c5d-8e9f-001122334455"})
    payload = AuthHandler.decode_token(token)
    assert payload["type"] == "refresh"
    assert "permissions" not in payload


@pytest.mark.asyncio
async def test_refresh_token_cannot_call_a_route():
    token = AuthHandler.create_refresh_token({"user_id": "6f0b4c3e-1a2b-4c5d-8e9f-001122334455"})
    with pytest.raises(HTTPException) as raised:
        await get_current_user(token)
    assert raised.value.status_code == 401


def test_hr_role_map_includes_case_actions_and_legal_does_not():
    hr = claims_for_role("HR")
    assert "case:open" in hr["permissions"]
    assert "case:confirm" in hr["permissions"]
    assert claims_for_role("LEGAL") == {"roles": ["LEGAL"], "permissions": []}
    assert claims_for_role("ADMIN")["permissions"] == []


@pytest.mark.asyncio
async def test_missing_permission_is_forbidden():
    guard = require_permissions(PermissionEnum.CASE_OPEN)
    with pytest.raises(HTTPException) as raised:
        await guard(current_user={"roles": ["LEGAL"], "permissions": [], "is_active": True})
    assert raised.value.status_code == 403


@pytest.mark.asyncio
async def test_hr_permission_passes():
    guard = require_permissions(PermissionEnum.CASE_CHAT)
    user = await guard(current_user={"roles": ["HR"], "permissions": ["case:chat"], "is_active": True, "user_id": "x"})
    assert user["roles"] == ["HR"]


@pytest.mark.asyncio
async def test_role_guard_rejects_legal_on_an_hr_route():
    guard = require_roles(RoleEnum.HR, RoleEnum.MANAGER)
    with pytest.raises(HTTPException) as raised:
        await guard(current_user={"roles": ["LEGAL"], "permissions": [], "is_active": True})
    assert raised.value.status_code == 403


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {
            "user_id": "6f0b4c3e-1a2b-4c5d-8e9f-001122334455",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as raised:
        AuthHandler.decode_token(expired)
    assert raised.value.status_code == 401


def test_password_hash_round_trip():
    hashed = AuthHandler.get_password_hash("mat-khau-1")
    assert AuthHandler.verify_password("mat-khau-1", hashed)
    assert not AuthHandler.verify_password("sai", hashed)
    assert not AuthHandler.verify_password("mat-khau-1", "khong-phai-hash")
