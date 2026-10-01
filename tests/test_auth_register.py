"""Registration contract. These checks stop before the database."""

import pytest
from pydantic import ValidationError

from src.common.auth import RegisterRequest
from src.core.security.rbac import RoleEnum


def test_register_request_folds_email_and_name():
    body = RegisterRequest(
        email="  HR@VinUni.edu.vn ",
        password="mat-khau-1",
        full_name="  Nguyễn Lan  ",
        role="manager",
    )
    assert body.email == "hr@vinuni.edu.vn"
    assert body.full_name == "Nguyễn Lan"
    assert body.role == RoleEnum.MANAGER


def test_register_defaults_to_hr_and_drops_a_blank_name():
    body = RegisterRequest(email="hr.moi@vinuni.edu.vn", password="mat-khau-1", full_name="   ")
    assert body.role == RoleEnum.HR
    assert body.full_name is None


def test_register_rejects_a_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="hr.moi@vinuni.edu.vn", password="ngan")


def test_register_rejects_an_unknown_role():
    with pytest.raises(ValidationError):
        RegisterRequest(email="hr.moi@vinuni.edu.vn", password="mat-khau-1", role="ADMIN")


@pytest.mark.asyncio
async def test_register_route_rejects_a_bad_email(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "khong-phai-email", "password": "mat-khau-1"},
    )
    assert response.status_code == 422
