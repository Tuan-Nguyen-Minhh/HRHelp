"""Read chunks whose policy version was in force on the incident date."""

from dataclasses import dataclass, replace
from datetime import date
from uuid import UUID

from sqlalchemy import bindparam, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

import src.common.orm  # noqa: F401
from src.core.config import settings
from src.features.cite.model.bm25 import bm25_rank
from src.features.cite.model.passage import GraphEdge, Passage
from src.models.chunk_references import ChunkReference
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
_TS_CONFIG = "simple"
_OR_TSQUERY = text(
    """
    SELECT COALESCE(
        string_agg(to_tsquery(CAST(:cfg AS regconfig), t.lexeme)::text, ' | '),
        ''
    )
    FROM unnest(to_tsvector(CAST(:cfg AS regconfig), :q)) AS t(lexeme)
    """
)


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


def graph_edge_stmt(seed_chunk_ids: list[UUID], *, incoming: bool, min_confidence: str = "HIGH"):
    """Indexed forward/reverse edge reads; ambiguous and external edges are excluded."""
    seed_column = ChunkReference.target_chunk_id if incoming else ChunkReference.source_chunk_id
    return (
        select(
            ChunkReference.source_chunk_id,
            ChunkReference.target_chunk_id,
            ChunkReference.rule,
            ChunkReference.confidence,
        )
        .where(
            seed_column.in_(seed_chunk_ids),
            ChunkReference.target_chunk_id.is_not(None),
            ChunkReference.confidence == min_confidence,
            ChunkReference.needs_review.is_(False),
        )
        .order_by(ChunkReference.source_chunk_id, ChunkReference.target_chunk_id, ChunkReference.ref_id)
    )


async def fetch_graph_neighbors(
    session: AsyncSession,
    incident_date: date,
    seed_chunk_ids: list[UUID],
    limit: int,
    *,
    min_confidence: str = "HIGH",
    exclude_chunk_ids: list[UUID] | tuple[UUID, ...] = (),
    include_incoming: bool = True,
) -> list[Passage]:
    """Read both directions once, then hydrate distinct in-force neighbors with provenance."""
    if not seed_chunk_ids or limit <= 0:
        return []
    edges: dict[UUID, list[GraphEdge]] = {}
    excluded = set(seed_chunk_ids) | set(exclude_chunk_ids)
    for incoming in ((False, True) if include_incoming else (False,)):
        rows = (
            await session.execute(graph_edge_stmt(seed_chunk_ids, incoming=incoming, min_confidence=min_confidence))
        ).all()
        for row in rows:
            seed = row.target_chunk_id if incoming else row.source_chunk_id
            neighbor = row.source_chunk_id if incoming else row.target_chunk_id
            if neighbor in excluded:
                continue
            edge = GraphEdge(seed, row.source_chunk_id, row.target_chunk_id, row.rule, row.confidence)
            provenance = edges.setdefault(neighbor, [])
            if edge not in provenance:
                provenance.append(edge)
    if not edges:
        return []
    # Apply the limit after eligibility filtering and deduplication, not to raw edges.
    stmt = _candidate_stmt(incident_date).where(DocumentChunk.id.in_(edges))
    rows = (await session.execute(stmt)).all()
    seed_order = {chunk_id: order for order, chunk_id in enumerate(seed_chunk_ids)}
    def priority(row):
        links = edges[row.chunk_id]
        return (min(seed_order[edge.seed_chunk_id] for edge in links),
                min(0 if edge.source_chunk_id == edge.seed_chunk_id else 1 for edge in links),
                -len({edge.seed_chunk_id for edge in links}), str(row.chunk_id))
    rows = sorted(rows, key=priority)[:limit]
    return [replace(to_passage(_hit(row)), origin="graph", graph_edges=tuple(edges[row.chunk_id])) for row in rows]


async def fetch_by_similarity(
    session: AsyncSession, incident_date: date, embedding: list[float], limit: int
) -> list[ChunkHit]:
    """Return the nearest in-force chunks. ``embedding`` must already match the column dimension."""
    distance = DocumentChunk.embedding.cosine_distance(embedding)
    stmt = _candidate_stmt(incident_date).where(DocumentChunk.embedding.is_not(None)).order_by(distance).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [_hit(row) for row in rows]


async def fetch_by_bm25(session: AsyncSession, incident_date: date, terms: list[str], limit: int,
                        *, policy_types: tuple[str, ...] | None = None) -> list[Passage]:
    """Okapi BM25 over the complete eligible corpus, not an arbitrary prefiltered sample.

    The bounded small-corpus implementation is intentional. If the corpus grows
    past the configured limit, fail this arm explicitly instead of corrupting IDF.
    """
    if not terms or limit <= 0:
        return []
    statement = _candidate_stmt(incident_date)
    if policy_types:
        statement = statement.where(Policy.policy_type.in_(policy_types))
    rows = (await session.execute(
        statement.order_by(DocumentChunk.id).limit(settings.RETRIEVAL_BM25_MAX_CORPUS + 1)
    )).all()
    if len(rows) > settings.RETRIEVAL_BM25_MAX_CORPUS:
        raise ValueError("BM25 eligible corpus exceeds configured limit; use an indexed BM25 backend")
    passages = [to_passage(_hit(row)) for row in rows]
    contextual = [replace(item, content=f"{item.section_title}\n{item.content}") for item in passages]
    ranked = bm25_rank(contextual, terms, limit)
    originals = {item.chunk_id: item for item in passages}
    return [replace(originals[item.chunk_id], score=item.score) for item in ranked]


async def fetch_by_fts(session: AsyncSession, incident_date: date, terms: list[str], limit: int) -> list[Passage]:
    """Rank every in-force chunk with ``ts_rank`` on ``document_chunks.search_tsv``.

    The column is the generated ``simple`` tsvector of ``section_title`` and
    ``content`` (migration 0004). Terms are OR-ed, so one matching lexeme is enough.
    """
    if not terms or limit <= 0:
        return []
    tsquery = await _or_tsquery(session, terms)
    if not tsquery:
        return []
    stmt = bm25_stmt(incident_date, limit)
    rows = (await session.execute(stmt, {"cfg": _TS_CONFIG, "tsq": tsquery})).all()
    return [replace(to_passage(_hit(row)), score=float(row.arm_score or 0.0)) for row in rows]


def bm25_stmt(incident_date: date, limit: int):
    """In-force chunks ordered by ``ts_rank``. ``:cfg`` is the regconfig, ``:tsq`` the OR query."""
    parsed = func.to_tsquery(text("CAST(:cfg AS regconfig)"), bindparam("tsq"))
    rank = func.ts_rank(DocumentChunk.search_tsv, parsed, 1).label("arm_score")
    return (
        _candidate_stmt(incident_date)
        .add_columns(rank)
        .where(DocumentChunk.search_tsv.bool_op("@@")(parsed))
        .order_by(rank.desc(), DocumentChunk.id)
        .limit(limit)
    )


async def _or_tsquery(session: AsyncSession, terms: list[str]) -> str:
    """Lexemes of ``terms`` joined with OR. Postgres quotes each lexeme."""
    found = (await session.execute(_OR_TSQUERY, {"cfg": _TS_CONFIG, "q": " ".join(terms)})).scalar_one()
    return found or ""


async def fetch_candidates(session: AsyncSession, incident_date: date, terms: list[str]) -> list[ChunkHit]:
    """Return chunks whose version covers ``incident_date`` and whose text hits a term."""
    if not terms:
        return []
    # Rank before LIMIT. Multiword conduct phrases carry more than generic words.
    matches = [_outline_ilike(term) for term in terms]
    rank = sum(case((match, 3 if " " in term else 1), else_=0) for term, match in zip(terms, matches, strict=True))
    stmt = (_candidate_stmt(incident_date).where(or_(*matches))
            .order_by(rank.desc(), DocumentChunk.id).limit(settings.RETRIEVAL_CANDIDATE_K))
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
            DocumentChunk.chunk_index.label("chunk_index"),
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
            DocumentChunk.section_title,
            DocumentChunk.chunk_metadata.label("chunk_metadata"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(PolicyVersion, PolicyVersion.id == Document.policy_version_id)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(
            in_force_filter(incident_date),
            Policy.is_active.is_(True),
            Policy.deleted_at.is_(None),
            Document.deleted_at.is_(None),
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
        section_title=hit.section_title or hit.article_title or "",
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
