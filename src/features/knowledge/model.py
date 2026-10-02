"""Register a policy version and ingest its text. Failed embeddings can be retried."""

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.audit import write_audit
from src.common.errors import AppError
from src.features.knowledge.schema import DocumentView, VersionCreate, VersionListResponse, VersionView
from src.models.document_chunks import DocumentChunk
from src.models.documents import Document
from src.models.policies import Policy
from src.models.policy_versions import PolicyVersion
from src.models.users import User

logger = logging.getLogger(__name__)

Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]


def split_chunks(content: str, limit: int = 1500) -> list[str]:
    """Split ingested text on blank lines, then on the size limit."""
    blocks = [part.strip() for part in content.split("\n\n") if part.strip()]
    if not blocks:
        blocks = [content.strip()]
    pieces: list[str] = []
    for block in blocks:
        while len(block) > limit:
            pieces.append(block[:limit])
            block = block[limit:]
        if block:
            pieces.append(block)
    return pieces


async def create_version(
    session: AsyncSession,
    actor: User,
    policy_id: UUID,
    payload: VersionCreate,
    embedder: Embedder | None = None,
) -> VersionView:
    """Add a non-overlapping version. Optional text is hashed, chunked, and embedded."""
    policy = await _policy(session, policy_id)
    if payload.effective_to is not None and payload.effective_to < payload.effective_from:
        raise AppError(422, "Ngày hết hiệu lực phải sau ngày bắt đầu.", code="UNPROCESSABLE")
    version = PolicyVersion(
        id=uuid4(),
        policy_id=policy.id,
        version=payload.version,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status=payload.status,
    )
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(409, "Phiên bản trùng hoặc khoảng hiệu lực chồng lên bản khác.", code="CONFLICT") from exc
    if payload.content and payload.content.strip():
        await _ingest(session, actor, version, payload.file_name or f"{policy.code}-{payload.version}.txt", payload.content, embedder)
    await session.commit()
    return _version_view(version)


async def list_versions(session: AsyncSession, policy_id: UUID) -> VersionListResponse:
    await _policy(session, policy_id)
    rows = list(
        (
            await session.scalars(
                select(PolicyVersion)
                .where(PolicyVersion.policy_id == policy_id)
                .order_by(PolicyVersion.effective_from.asc())
            )
        ).all()
    )
    return VersionListResponse(versions=[_version_view(row) for row in rows])


async def get_document(session: AsyncSession, document_id: UUID) -> DocumentView:
    document = await _document(session, document_id)
    total, embedded = await _chunk_counts(session, document.id)
    return _document_view(document, total, embedded)


async def retry_document(
    session: AsyncSession,
    actor: User,
    document_id: UUID,
    embedder: Embedder | None = None,
) -> DocumentView:
    """Embed chunks that still have no vector. A successful document is left alone."""
    document = await _document(session, document_id)
    chunks = list(
        (
            await session.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index)
            )
        ).all()
    )
    pending = [chunk for chunk in chunks if chunk.embedding is None]
    if document.ingest_status == "EMBEDDED" and not pending:
        raise AppError(409, "Văn bản đã embed xong.", code="CONFLICT")
    if not pending:
        document.ingest_status = "FAILED"
        await session.commit()
        raise AppError(409, "Không còn đoạn nào để embed lại.", code="DOCUMENT_INGESTION_FAILED")
    try:
        vectors = await _vectors(embedder, [chunk.content for chunk in pending])
        for chunk, vector in zip(pending, vectors, strict=True):
            chunk.embedding = vector
        document.ingest_status = "EMBEDDED"
    except Exception as exc:
        logger.exception("document retry failed")
        document.ingest_status = "FAILED"
        await write_audit(
            session,
            case_id=None,
            actor_id=actor.id,
            actor_role=actor.role,
            action="DOCUMENT_RETRIED",
            entity_type="documents",
            entity_id=document.id,
            after={"ingest_status": "FAILED"},
        )
        await session.commit()
        raise AppError(503, "Embed lại thất bại.", code="DOCUMENT_INGESTION_FAILED") from exc
    await write_audit(
        session,
        case_id=None,
        actor_id=actor.id,
        actor_role=actor.role,
        action="DOCUMENT_RETRIED",
        entity_type="documents",
        entity_id=document.id,
        after={"ingest_status": document.ingest_status},
    )
    await session.commit()
    total, embedded = await _chunk_counts(session, document.id)
    return _document_view(document, total, embedded)


async def _ingest(
    session: AsyncSession,
    actor: User,
    version: PolicyVersion,
    file_name: str,
    content: str,
    embedder: Embedder | None,
) -> None:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    duplicate = await session.scalar(
        select(Document.id).where(Document.content_hash == digest, Document.deleted_at.is_(None))
    )
    if duplicate is not None:
        raise AppError(409, "Nội dung này đã được nạp.", code="DOCUMENT_DUPLICATE")
    document = Document(
        id=uuid4(),
        policy_version_id=version.id,
        file_name=file_name,
        file_type="text/plain",
        content_hash=digest,
        ingest_status="UPLOADED",
    )
    session.add(document)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(409, "Nội dung này đã được nạp.", code="DOCUMENT_DUPLICATE") from exc
    pieces = split_chunks(content)
    chunks = []
    for index, piece in enumerate(pieces):
        chunk = DocumentChunk(id=uuid4(), document_id=document.id, chunk_index=index, content=piece)
        session.add(chunk)
        chunks.append(chunk)
    document.ingest_status = "CHUNKED"
    await session.flush()
    try:
        vectors = await _vectors(embedder, pieces)
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        document.ingest_status = "EMBEDDED"
    except Exception:
        logger.exception("document embed failed")
        document.ingest_status = "FAILED"
    await write_audit(
        session,
        case_id=None,
        actor_id=actor.id,
        actor_role=actor.role,
        action="DOCUMENT_INGESTED",
        entity_type="documents",
        entity_id=document.id,
        after={"ingest_status": document.ingest_status, "content_hash": digest},
    )


async def _vectors(embedder: Embedder | None, pieces: list[str]) -> list[list[float]]:
    if embedder is not None:
        return await embedder(pieces)

    def _call() -> list[list[float]]:
        from src.services.embeddings_client import PURPOSE_CORPUS, EmbeddingClient

        client = EmbeddingClient()
        return client.embed(pieces, purpose=PURPOSE_CORPUS, run_id="ingest", chunk_ids=[str(index) for index in range(len(pieces))])

    return await asyncio.to_thread(_call)


async def _policy(session: AsyncSession, policy_id: UUID) -> Policy:
    policy = await session.get(Policy, policy_id)
    if policy is None or policy.deleted_at is not None:
        raise AppError(404, "Không tìm thấy chính sách.", code="NOT_FOUND")
    return policy


async def _document(session: AsyncSession, document_id: UUID) -> Document:
    document = await session.get(Document, document_id)
    if document is None or document.deleted_at is not None:
        raise AppError(404, "Không tìm thấy văn bản.", code="NOT_FOUND")
    return document


async def _chunk_counts(session: AsyncSession, document_id: UUID) -> tuple[int, int]:
    total = await session.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id))
    embedded = await session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_not(None))
    )
    return int(total or 0), int(embedded or 0)


def _version_view(row: PolicyVersion) -> VersionView:
    return VersionView(
        id=row.id,
        policy_id=row.policy_id,
        version=row.version,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        status=row.status,
        created_at=row.created_at,
    )


def _document_view(document: Document, total: int, embedded: int) -> DocumentView:
    return DocumentView(
        id=document.id,
        policy_version_id=document.policy_version_id,
        file_name=document.file_name,
        ingest_status=document.ingest_status,
        content_hash=document.content_hash,
        chunk_count=total,
        embedded_chunk_count=embedded,
    )
