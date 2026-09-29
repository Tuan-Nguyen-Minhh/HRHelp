"""Read chunks whose policy version was in force on the incident date."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

import src.common.orm  # noqa: F401
from src.features.cite.model.passage import Passage
from src.models.document_chunks import DocumentChunk
from src.models.documents import Document
from src.models.policies import Policy
from src.models.policy_versions import PolicyVersion


@dataclass(frozen=True)
class ChunkHit:
    """One in-force chunk, before it is scored or placed in a layer."""

    chunk_id: UUID
    policy_version_id: UUID
    content: str
    article: str | None
    clause: str | None
    point: str | None
    policy_type: str | None
    policy_code: str
    policy_name: str
    section_title: str | None = None
    chunk_index: int = 0
    article_title: str | None = None


CANDIDATE_LIMIT = 40
_READABLE = ("CHUNKED", "EMBEDDED")


def in_force_filter(incident_date: date) -> ColumnElement[bool]:
    """Versions active on the incident date. ``effective_to`` is inclusive."""
    return (
        (PolicyVersion.status == "ACTIVE")
        & (PolicyVersion.effective_from <= incident_date)
        & ((PolicyVersion.effective_to.is_(None)) | (PolicyVersion.effective_to >= incident_date))
    )


async def fetch_in_force(session: AsyncSession, incident_date: date, limit: int) -> list[ChunkHit]:
    """Return in-force chunks with no term filter, for BM25 and any full-window retriever."""
    stmt = _candidate_stmt(incident_date).order_by(DocumentChunk.id).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [_hit(row) for row in rows]


async def fetch_by_similarity(
    session: AsyncSession, incident_date: date, embedding: list[float], limit: int
) -> list[ChunkHit]:
    """Return the nearest in-force chunks. ``embedding`` must already match the column dimension."""
    distance = DocumentChunk.embedding.cosine_distance(embedding)
    stmt = (
        _candidate_stmt(incident_date)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [_hit(row) for row in rows]


async def fetch_candidates(session: AsyncSession, incident_date: date, terms: list[str]) -> list[ChunkHit]:
    """Return chunks whose version covers ``incident_date`` and whose text hits a term."""
    if not terms:
        return []
    stmt = _candidate_stmt(incident_date).where(or_(*[_ilike(term) for term in terms])).limit(CANDIDATE_LIMIT)
    rows = (await session.execute(stmt)).all()
    return [_hit(row) for row in rows]


async def fetch_article_index(
    session: AsyncSession, incident_date: date, phrases: list[str], limit: int
) -> list[ChunkHit]:
    """Return one in-force chunk per article whose outline or text contains a phrase."""
    if not phrases or limit <= 0:
        return []
    rows = (await session.execute(article_index_stmt(incident_date, phrases, limit))).all()
    return [_hit(row) for row in rows]


def article_index_stmt(incident_date: date, phrases: list[str], limit: int):
    """Distinct article heads. Callers sort and cap the handoff list afterwards."""
    return (
        _candidate_stmt(incident_date)
        .add_columns(
            DocumentChunk.section_title.label("section_title"),
            DocumentChunk.chunk_index.label("chunk_index"),
            DocumentChunk.chunk_metadata.label("chunk_metadata"),
        )
        .where(or_(*[_outline_ilike(phrase) for phrase in phrases]))
        .distinct(PolicyVersion.id, DocumentChunk.article)
        .order_by(PolicyVersion.id, DocumentChunk.article, DocumentChunk.chunk_index)
        .limit(limit)
    )


def _candidate_stmt(incident_date: date):
    return (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.content,
            DocumentChunk.article,
            DocumentChunk.clause,
            DocumentChunk.point,
            PolicyVersion.id.label("policy_version_id"),
            Policy.policy_type,
            Policy.code.label("policy_code"),
            Policy.name.label("policy_name"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(PolicyVersion, PolicyVersion.id == Document.policy_version_id)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(
            in_force_filter(incident_date),
            Policy.is_active.is_(True),
            Document.ingest_status.in_(_READABLE),
        )
    )


def _ilike(term: str) -> ColumnElement[bool]:
    return _ilike_column(DocumentChunk.content, term)


def _outline_ilike(phrase: str) -> ColumnElement[bool]:
    title = DocumentChunk.chunk_metadata["article_title"].astext
    return or_(
        _ilike_column(DocumentChunk.content, phrase),
        _ilike_column(DocumentChunk.section_title, phrase),
        _ilike_column(title, phrase),
    )


def _ilike_column(column, term: str) -> ColumnElement[bool]:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


def to_passage(hit: ChunkHit) -> Passage:
    """A retrieved chunk before a retriever writes its own score."""
    return Passage(
        chunk_id=hit.chunk_id,
        policy_version_id=hit.policy_version_id,
        content=hit.content,
        article=hit.article,
        clause=hit.clause,
        point=hit.point,
        score=0.0,
        policy_type=hit.policy_type,
        policy_code=hit.policy_code,
        policy_name=hit.policy_name,
    )


def _hit(row: object) -> ChunkHit:
    return ChunkHit(
        chunk_id=row.chunk_id,
        policy_version_id=row.policy_version_id,
        content=row.content,
        article=row.article,
        clause=row.clause,
        point=row.point,
        policy_type=row.policy_type,
        policy_code=row.policy_code,
        policy_name=row.policy_name,
        section_title=getattr(row, "section_title", None),
        chunk_index=int(getattr(row, "chunk_index", 0) or 0),
        article_title=_article_title(getattr(row, "chunk_metadata", None)),
    )


def _article_title(metadata: object) -> str | None:
    if not isinstance(metadata, dict):
        return None
    title = metadata.get("article_title")
    if not isinstance(title, str):
        return None
    stripped = title.strip()
    return stripped or None
