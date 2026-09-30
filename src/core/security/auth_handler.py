"""Password hashes and JWT access/refresh tokens.

An access token carries roles and permissions taken at login. A refresh token
does not, so the next access token can see a role change.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from src.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthHandler:
    SECRET_KEY = settings.JWT_SECRET
    ALGORITHM = settings.JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except (ValueError, TypeError):
            return False

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return pwd_context.hash(password)

    @classmethod
    def create_access_token(
        cls,
        data: dict[str, Any],
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> str:
        """Embed roles and permissions so a later request does not read them again."""
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update(
            {
                "exp": expire,
                "type": "access",
                "roles": list(roles or []),
                "permissions": list(permissions or []),
            }
        )
        return jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def create_refresh_token(cls, data: dict[str, Any]) -> str:
        """A refresh token names the user only. Refresh loads roles from the database."""
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def decode_token(cls, token: str) -> dict[str, Any]:
        """Return the claims, or 401 when the token is expired or malformed."""
        try:
            return jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token hết hạn.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
