"""Contracts for the admin document-ingestion surface."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IngestionDocumentView(BaseModel):
    document_id: UUID
    file_name: str
    ingest_status: str
    policy_code: str | None
    policy_name: str | None
    chunk_count: int
    embedded_chunk_count: int
    error: str | None
    created_at: datetime


class IngestionDocumentList(BaseModel):
    documents: list[IngestionDocumentView]
