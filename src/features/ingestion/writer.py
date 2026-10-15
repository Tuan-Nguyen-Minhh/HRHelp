"""Write an ingested document into the official runtime tables.

Rows are appended to ``policies``/``policy_versions``/``documents``/
``document_chunks``/``chunk_references`` — the same tables the existing corpus
lives in, so the agent retrieves the new document with no extra wiring. Nothing
existing is deleted or updated.
"""

import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_pipeline_steps.step3.cross_reference_resolver import KNOWN_LAW_PREFIXES
from src.common.audit import write_audit
from src.common.errors import AppError
from src.models.chunk_references import (
    NEEDS_REASON_BOUNDARY,
    NEEDS_REASON_UNRESOLVED,
    ChunkReference,
)
from src.models.document_chunks import DocumentChunk
from src.models.documents import Document
from src.models.policies import Policy
from src.models.policy_versions import PolicyVersion
from src.models.users import User

from .metadata import policy_type_for
from .pipeline import Ingested, Preprocessed

# Keys promoted to dedicated columns (mirrors scripts/seed_legal.py); everything
# else in ChunkMetadata stays in the chunk_metadata JSONB.
_SEPARATE_KEYS = (
    "document_id",
    "document_type",
    "document_form",
    "article_number",
    "clause_number",
    "point_letter",
    "chunk_level",
)
_LEVEL_RANK = {"ARTICLE": 0, "CLAUSE": 1, "POINT": 2}
_LAW_NUMBER_RE = re.compile(r"^\d{2,3}/20\d{2}/[A-ZĐ0-9-]+$")


def content_hash(cleaned_text: str) -> str:
    return hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()


def embedding_input(chunk: DocumentChunk) -> str:
    """Same shape ``scripts/embed_legal.py`` embeds: breadcrumb + body."""
    return f"{chunk.section_title or ''}\n{chunk.content}"


def _stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


async def existing_codes(session: AsyncSession) -> set[str]:
    return set((await session.scalars(select(Policy.code))).all())


async def write_document(
    session: AsyncSession,
    actor: User,
    *,
    filename: str,
    file_type: str | None,
    prep: Preprocessed,
    ingested: Ingested,
    effective_from,
) -> Document:
    """Insert the whole document graph. The caller commits."""
    doc_info = ingested.doc_info

    policy = Policy(
        id=uuid4(),
        code=doc_info["doc_code"],
        name=(prep.metadata.get("document_title") or doc_info["doc_code"])[:255],
        policy_type=policy_type_for(doc_info["document_type"]),
        is_active=True,
    )
    session.add(policy)
    await session.flush()

    version = PolicyVersion(
        id=uuid4(),
        policy_id=policy.id,
        version="1.0",
        effective_from=effective_from,
        effective_to=None,
        status="ACTIVE",
    )
    session.add(version)
    await session.flush()

    document = Document(
        id=uuid4(),
        policy_version_id=version.id,
        file_name=filename[:255],
        file_type=file_type,
        source=f"upload:{actor.id}:{_stamp()}",
        content_hash=content_hash(prep.content),
        ingest_status="CHUNKED",
    )
    session.add(document)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(409, "Nội dung này đã được nạp trước đó.", code="DOCUMENT_DUPLICATE") from exc

    chunk_rows = _build_chunks(document.id, ingested)
    for row in chunk_rows:
        session.add(row)
    await session.flush()

    await _write_references(session, ingested, chunk_rows)

    await write_audit(
        session,
        case_id=None,
        actor_id=actor.id,
        actor_role=actor.role,
        action="DOCUMENT_INGESTED",
        entity_type="documents",
        entity_id=document.id,
        after={"ingest_status": "CHUNKED", "chunk_count": len(chunk_rows), "doc_code": doc_info["doc_code"]},
    )
    return document


def _build_chunks(document_id: UUID, ingested: Ingested) -> list[DocumentChunk]:
    rows: list[DocumentChunk] = []
    for index, item in enumerate(ingested.chunks):
        meta = item.metadata.to_dict()
        for key in _SEPARATE_KEYS:
            meta.pop(key, None)
        meta["legal_chunk_id"] = item.chunk_id
        meta["legal_document_id"] = ingested.doc_info["document_id"]
        rows.append(
            DocumentChunk(
                id=uuid4(),
                document_id=document_id,
                chunk_index=index,
                content=item.text,
                section=item.metadata.chunk_level,
                section_title=item.header_context,
                article=str(item.metadata.article_number),
                clause=str(item.metadata.clause_number) if item.metadata.clause_number is not None else None,
                point=item.metadata.point_letter,
                chunk_metadata=meta,
                embedding=None,
            )
        )
    return rows


class _TargetIndex:
    """Level-aware resolver from (document, article, clause, point) to a chunk UUID.

    Same contract as ``scripts/seed_legal.py::ChunkIndex``, rebuilt from the DB so
    it always reflects the live corpus (plus the rows just inserted).
    """

    def __init__(self) -> None:
        self.by_clause: dict[tuple, UUID] = {}
        self.by_point: dict[tuple, UUID] = {}
        self._rep: dict[tuple, tuple] = {}

    def add(self, doc: str | None, article: str | None, clause: str | None,
            point: str | None, level: str | None, chunk_id: UUID) -> None:
        if not doc or not article or not article.isdigit():
            return
        art = int(article)
        cl = int(clause) if clause and clause.isdigit() else None
        pt = point.lower() if point else None
        if level == "CLAUSE" and cl is not None:
            self.by_clause[(doc, art, cl)] = chunk_id
        elif level == "POINT" and cl is not None and pt:
            self.by_point[(doc, art, cl, pt)] = chunk_id
        rank = _LEVEL_RANK.get(level or "", 3)
        candidate = (rank, cl if cl is not None else -1, pt or "", str(chunk_id))
        key = (doc, art)
        if key not in self._rep or candidate < self._rep[key]:
            self._rep[key] = candidate

    def resolve(self, target_doc: str, article: int, clause: int | None, point: str | None) -> UUID | None:
        if point is not None and clause is not None:
            hit = self.by_point.get((target_doc, article, clause, point.lower()))
            if hit:
                return hit
        if clause is not None:
            hit = self.by_clause.get((target_doc, article, clause))
            if hit:
                return hit
        rep = self._rep.get((target_doc, article))
        return UUID(rep[3]) if rep else None


async def _target_index(session: AsyncSession) -> tuple[_TargetIndex, set[str]]:
    rows = (
        await session.execute(
            select(
                DocumentChunk.id,
                DocumentChunk.article,
                DocumentChunk.clause,
                DocumentChunk.point,
                DocumentChunk.section,
                DocumentChunk.chunk_metadata["legal_document_id"].astext,
            )
        )
    ).all()
    index = _TargetIndex()
    internal: set[str] = set()
    for chunk_id, article, clause, point, level, doc in rows:
        if doc:
            internal.add(doc)
        index.add(doc, article, clause, point, level, chunk_id)
    return index, internal


def _needs_reason(target_doc: str, rule: str, confidence: str, internal: set[str]) -> str | None:
    if target_doc not in internal and not _LAW_NUMBER_RE.match(target_doc) and target_doc not in KNOWN_LAW_PREFIXES:
        return NEEDS_REASON_UNRESOLVED
    if rule == "BOUNDARY_CHECK" or confidence == "LOW":
        return NEEDS_REASON_BOUNDARY
    return None


async def _write_references(session: AsyncSession, ingested: Ingested, chunk_rows: list[DocumentChunk]) -> None:
    if not ingested.chunks:
        return
    index, internal = await _target_index(session)
    internal.add(ingested.tree.document_id)

    rows: list[dict] = []
    seen: set[tuple] = set()
    for item, chunk_row in zip(ingested.chunks, chunk_rows, strict=True):
        for ref in item.references:
            target = index.resolve(ref.target_doc, ref.article, ref.clause, ref.point)
            reason = _needs_reason(ref.target_doc, ref.rule, ref.confidence, internal)
            key = (chunk_row.id, target, ref.target_doc, ref.article, ref.clause, ref.point, ref.rule)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source_chunk_id": chunk_row.id,
                    "target_chunk_id": target,
                    "target_doc": ref.target_doc[:128],
                    "article": ref.article,
                    "clause": ref.clause,
                    "point": ref.point,
                    "rule": ref.rule[:64],
                    "confidence": ref.confidence,
                    "needs_review": reason is not None,
                    "needs_reason": reason,
                }
            )
    if rows:
        await session.execute(insert(ChunkReference), rows)
