"""Request and response models for opening a case."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OpenCaseRequest(BaseModel):
    """Body of ``POST /cases``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    case_code: str = Field(min_length=1, max_length=100, description="Mã hồ sơ, duy nhất")
    employee_code: str = Field(min_length=1, max_length=100)
    employee_name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=8000, description="Mô tả tình huống")
    incident_date: date = Field(description="Ngày xảy ra việc, mốc lọc văn bản còn hiệu lực")


class OpenCaseResponse(BaseModel):
    """Ids the chat screen needs after a case is opened."""

    case_id: UUID
    conversation_id: UUID
    status: str


class CaseView(BaseModel):
    """Header of one case plus its active conversation."""

    case_id: UUID
    conversation_id: UUID | None
    case_code: str
    employee_code: str | None
    employee_name: str | None
    description: str | None
    incident_date: date | None
    status: str
