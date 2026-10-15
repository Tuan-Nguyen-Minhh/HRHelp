"""Orchestrate an admin upload end to end.

Phase 1 runs in the request: convert, preprocess, chunk, and insert the document
graph with NULL embeddings (``ingest_status = CHUNKED``). Phase 2 (embedding) is
scheduled in the background. Failures in phase 1 surface as an HTTP error and
leave nothing behind; failures in phase 2 mark the document ``FAILED`` and are
retryable.
"""

from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.models.audit_logs import AuditLog
from src.models.document_chunks import DocumentChunk
from src.models.documents import Document
from src.models.policies import Policy
from src.models.policy_versions import PolicyVersion
from src.models.users import User

from . import converter, embedding, metadata, pipeline, writer
from .schema import IngestionDocumentList, IngestionDocumentView

_LIST_LIMIT = 100


async def create_from_upload(
    session: AsyncSession,
    actor: User,
    *,
    filename: str,
    data: bytes,
    effective_from: date | None,
) -> IngestionDocumentView:
    if not (filename or "").strip():
        raise AppError(422, "Thiếu tên tệp.", code="UNPROCESSABLE")

    markdown = converter.to_markdown(filename, data)
    prep = pipeline.preprocess(markdown, filename)
    stem = Path(filename).stem
    doc_info = metadata.build_doc_info(prep.metadata, stem, await writer.existing_codes(session))
    ingested = pipeline.chunk(prep.content, stem, doc_info)
    if not ingested.chunks:
        raise AppError(422, "Không tách được Điều nào từ văn bản.", code="NO_ARTICLES")

    document = await writer.write_document(
        session,
        actor,
        filename=filename,
        file_type=Path(filename).suffix.lstrip(".").lower() or None,
        prep=prep,
        ingested=ingested,
        effective_from=effective_from or date.today(),
    )
    await session.commit()
    embedding.schedule(embedding.embed_document(document.id, actor.id))
    return await get_document(session, document.id)


async def list_documents(session: AsyncSession) -> IngestionDocumentList:
    rows = (
        await session.execute(
            _document_query()
            .where(Document.source.like("upload:%"), Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .limit(_LIST_LIMIT)
        )
    ).all()
    documents = [await _view(session, doc, code, name) for doc, code, name in rows]
    return IngestionDocumentList(documents=documents)


async def get_document(session: AsyncSession, document_id: UUID) -> IngestionDocumentView:
    row = (await session.execute(_document_query().where(Document.id == document_id))).first()
    if row is None:
        raise AppError(404, "Không tìm thấy văn bản.", code="NOT_FOUND")
    document, code, name = row
    return await _view(session, document, code, name)


async def retry_document(session: AsyncSession, actor: User, document_id: UUID) -> IngestionDocumentView:
    document = await session.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        raise AppError(404, "Không tìm thấy văn bản.", code="NOT_FOUND")
    total, embedded = await _counts(session, document_id)
    if document.ingest_status == "EMBEDDED" and embedded >= total:
        raise AppError(409, "Văn bản đã embed xong.", code="CONFLICT")
    document.ingest_status = "CHUNKED"
    await session.commit()
    embedding.schedule(embedding.embed_document(document.id, actor.id))
    return await get_document(session, document_id)


def _document_query():
    return (
        select(Document, Policy.code, Policy.name)
        .join(PolicyVersion, PolicyVersion.id == Document.policy_version_id)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
    )


async def _view(session: AsyncSession, document: Document, code: str | None, name: str | None) -> IngestionDocumentView:
    total, embedded = await _counts(session, document.id)
    return IngestionDocumentView(
        document_id=document.id,
        file_name=document.file_name,
        ingest_status=document.ingest_status,
        policy_code=code,
        policy_name=name,
        chunk_count=total,
        embedded_chunk_count=embedded,
        error=await _latest_error(session, document.id),
        created_at=document.created_at,
    )


async def _counts(session: AsyncSession, document_id: UUID) -> tuple[int, int]:
    total = await session.scalar(
        select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    embedded = await session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_not(None))
    )
    return int(total or 0), int(embedded or 0)


async def _latest_error(session: AsyncSession, document_id: UUID) -> str | None:
    meta = await session.scalar(
        select(AuditLog.audit_metadata)
        .where(
            AuditLog.entity_type == "documents",
            AuditLog.entity_id == document_id,
            AuditLog.action == "DOCUMENT_INGEST_FAILED",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    if isinstance(meta, dict) and meta.get("error"):
        return str(meta["error"])
    return None
