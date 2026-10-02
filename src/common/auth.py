"""Login, registration, refresh, logout, and the current user."""

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.dependencies import get_current_active_user
from src.core.security.rbac import RoleEnum
from src.core.security.tokens import authenticate, refresh_access, register_account, revoke_refresh
from src.models.users import User

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


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MeResponse(BaseModel):
    """The signed-in user. The password hash is never included."""

    user_id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    roles: list[str]
    permissions: list[str]


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
        public = {RoleEnum.HR.value, RoleEnum.MANAGER.value, RoleEnum.LEGAL.value}
        if text not in public:
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


@router.post("/logout", status_code=204)
async def logout(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: Annotated[LogoutRequest | None, Body()] = None,
) -> None:
    """Retire a refresh token. The access token remains valid until it expires."""
    if body is not None and body.refresh_token:
        await revoke_refresh(session, actor.id, body.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(
    actor: Annotated[User, Depends(get_actor)],
    current: Annotated[dict[str, Any], Depends(get_current_active_user)],
) -> MeResponse:
    """Who the access token belongs to."""
    return MeResponse(
        user_id=actor.id,
        email=actor.email,
        full_name=actor.full_name,
        role=actor.role,
        is_active=bool(actor.is_active),
        roles=list(current.get("roles") or []),
        permissions=list(current.get("permissions") or []),
    )
