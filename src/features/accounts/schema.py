"""Account bodies a manager may send. Roles stay HR or LEGAL."""

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
StaffRole = Literal["HR", "LEGAL"]


class StaffAccount(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool


class StaffList(BaseModel):
    users: list[StaffAccount]


class StaffCreate(BaseModel):
    """A new HR or legal account. The manager types the first password."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=255)
    password: str
    full_name: str | None = Field(default=None, max_length=255)
    role: StaffRole

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
        return _password(value)

    @field_validator("full_name")
    @classmethod
    def empty_name_is_missing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class StaffUpdate(BaseModel):
    """Fields the manager chose to change. An omitted field stays as stored."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str | None = Field(default=None, max_length=255)
    password: str | None = None
    full_name: str | None = Field(default=None, max_length=255)
    role: StaffRole | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def fold_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip().casefold()
        if _EMAIL.fullmatch(email) is None:
            raise ValueError("Email không hợp lệ.")
        return email

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return _password(value)

    @field_validator("full_name")
    @classmethod
    def blank_name_clears(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def something_changed(self) -> "StaffUpdate":
        if self.email is None and self.password is None and self.role is None and self.is_active is None:
            if "full_name" not in self.model_fields_set:
                raise ValueError("Chưa có mục nào để sửa.")
        return self


def _password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Mật khẩu cần ít nhất 8 ký tự.")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Mật khẩu dài quá 72 byte.")
    return value
