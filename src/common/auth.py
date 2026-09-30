"""Login and refresh. The token is what later routes authorize against."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_session
from src.core.security.tokens import authenticate, refresh_access

router = APIRouter(prefix="/auth", tags=["Đăng nhập"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID
    roles: list[str] = Field(default_factory=list)


class RefreshToken(BaseModel):
    refresh_token: str


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
