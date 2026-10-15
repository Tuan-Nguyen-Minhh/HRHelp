"""Request and response models for opening a case."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.common.text import UppercaseText

FamilyName = Literal["UNAUTHORIZED_ABSENCE", "LATE", "GENERAL"]


class OpenCaseRequest(BaseModel):
    """Body of ``POST /cases``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    case_code: UppercaseText = Field(min_length=1, max_length=100, description="Mã hồ sơ, duy nhất")
    employee_code: UppercaseText = Field(min_length=1, max_length=100)
    employee_name: UppercaseText = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=8000, description="Mô tả tình huống")
    incident_date: date = Field(description="Ngày xảy ra việc, mốc lọc văn bản còn hiệu lực")
    family: FamilyName | None = None


class OpenCaseResponse(BaseModel):
    """Ids the chat screen needs after a case is opened."""

    case_id: UUID
    conversation_id: UUID
    status: str


class CaseView(BaseModel):
    """Header of one case plus its active conversation."""

    case_id: UUID
    conversation_id: UUID | None
    case_code: UppercaseText
    employee_code: UppercaseText | None
    employee_name: UppercaseText | None
    description: str | None
    incident_date: date | None
    status: str
    family: str | None = None


class CaseListResponse(BaseModel):
    """Cases the caller created or was granted."""

    cases: list[CaseView]


class CasePatchRequest(BaseModel):
    """Fields HR may correct before the case leaves the editable states."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    employee_code: UppercaseText | None = Field(default=None, min_length=1, max_length=100)
    employee_name: UppercaseText | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=8000)
    incident_date: date | None = None
    family: FamilyName | None = None


class AccessGrantRequest(BaseModel):
    """Grant or replace one user's access. ``revoke`` removes the grant."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    access_level: Literal["VIEW", "REVIEW", "EDIT"] | None = None
    revoke: bool = False


class AccessGrantView(BaseModel):
    user_id: UUID
    access_level: str
    granted_by: UUID | None
    created_at: datetime


class AccessListResponse(BaseModel):
    case_id: UUID
    grants: list[AccessGrantView]


class ReopenRequest(BaseModel):
    """Where a rejected case should return. Omitted means the server decides."""

    model_config = ConfigDict(extra="forbid")

    target: Literal["NEED_INFO", "ANALYZED"] | None = None


class ReopenResponse(BaseModel):
    case_id: UUID
    status: str
