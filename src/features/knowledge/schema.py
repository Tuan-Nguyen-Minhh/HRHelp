"""Version and document contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VersionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    version: str = Field(min_length=1, max_length=50)
    effective_from: date
    effective_to: date | None = None
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] = "ACTIVE"
    file_name: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=200_000)


class VersionView(BaseModel):
    id: UUID
    policy_id: UUID
    version: str
    effective_from: date
    effective_to: date | None
    status: str
    created_at: datetime


class VersionListResponse(BaseModel):
    versions: list[VersionView]


class DocumentView(BaseModel):
    id: UUID
    policy_version_id: UUID
    file_name: str
    ingest_status: str
    content_hash: str | None
    chunk_count: int
    embedded_chunk_count: int
