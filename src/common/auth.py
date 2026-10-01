"""Login, registration, and refresh. The token is what later routes authorize against."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_session
from src.core.security.rbac import RoleEnum
from src.core.security.tokens import authenticate, refresh_access, register_account

router = APIRouter(prefix="/auth", tags=["Đăng nhập"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID
    roles: list[str] = Field(default_factory=list)


class RefreshToken(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    """Body of ``POST /auth/register``. The new account is active immediately."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=255)
    password: str
    full_name: str | None = Field(default=None, max_length=255)
    role: RoleEnum = RoleEnum.HR

    @field_validator("email")
    @classmethod
    def fold_email(cls, value: str) -> str:
        email = value.strip().casefold()
        if _EMAIL.fullmatch(email) is None:
            raise ValueError("Email không hợp lệ.")
        return email

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Mật khẩu cần ít nhất 8 ký tự.")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mật khẩu dài quá 72 byte.")
        return value

    @field_validator("full_name")
    @classmethod
    def empty_name_is_missing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("role", mode="before")
    @classmethod
    def known_role(cls, value: object) -> object:
        if value is None or value == "":
            return RoleEnum.HR
        text = str(value).strip().upper()
        if text not in {item.value for item in RoleEnum}:
            raise ValueError("Vai trò phải là HR, MANAGER hoặc LEGAL.")
        return text


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Tạo tài khoản và trả token. HR và MANAGER mở hồ sơ. LEGAL chưa có quyền vụ việc."""
    result = await register_account(session, body.email, body.password, body.full_name, body.role.value)
    return TokenResponse(**result)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Đăng nhập bằng email (ô username) và mật khẩu. Token mang role và permission."""
    result = await authenticate(session, form.username, form.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu, hoặc tài khoản đã khóa.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshToken,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Cấp access token mới theo role và permission đang lưu."""
    return TokenResponse(**await refresh_access(session, body.refresh_token))
