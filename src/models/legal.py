"""SQLAlchemy models for the legal corpus (B4: metadata, B5: graph, B6: vectors).

Tables live under the ``legal_`` prefix on purpose: the generic application
tables (``documents``, ``document_chunks``, ...) belong to the HR Help bounded
context on ``main``. Both contexts share one Postgres database, so the legal
corpus gets its own namespace instead of colliding on ``documents``.

B4: legal_documents + legal_chunks (metadata & effectiveness)
B5: legal_chunk_references (cross-reference graph)
B6: legal_chunk_embeddings (mistral-embed vectors + BM25 tsvector)

All tables have created_at/updated_at. parent_chunk_id is TEXT with NO FK
constraint (dangling values exist by design — see V3-ter).

Column decisions that are easy to get wrong:

* ``parent_chunk_id`` deliberately has no ForeignKey. Every non-null value in the
  current dataset dangles (0 resolve), which is inherited from step3's
  chunking design. Adding an FK would make the seed impossible to run.
* The JSONB columns use ``none_as_null=True``. SQLAlchemy's default serialises a
  Python None as JSON ``null``, which is *not* SQL NULL — so ``amended_by IS NULL``
  would silently not match the two documents that have no footnotes.
* ``legal_chunk_embeddings`` repeats ``legal_chunks.header_context`` / ``.text``
  on purpose. A GENERATED column can only read columns of its own table, and the
  plan puts the BM25 ``search_tsv`` generated column on the embeddings table
  (plan 3.4, "chung với tạo bảng") so that B7 never has to modify the B4 tables.
  The copies are not a second source of truth: the FK is ON DELETE CASCADE, and
  verify_embeddings V2 asserts every copy byte-equals its ``legal_chunks``
  original, so drift is a FAIL, not a silent inconsistency.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

# ---------------------------------------------------------------------------
# Frozen embedding contract (DECISION 2026-09-26: ONE model for the whole DB)
# ---------------------------------------------------------------------------
# mistral-embed, 1024-dim. Hard-coded here on purpose: alembic/versions/0003
# hard-codes the same numbers, and changing either one must be a reviewed
# migration, never a silent config flip. scripts/embed_legal.py asserts that
# .env still agrees before spending a single token of quota.
EMBEDDING_MODEL_NAME = "mistral-embed"
EMBEDDING_DIM = 1024
# Postgres has no Vietnamese stemmer, so the BM25 tsvector config is 'simple'
# (whitespace/word splitting + exact match, no compound splitting). Good enough
# for legal terminology (article numbers, document names), and the plan
# explicitly forbids over-claiming beyond that.
BM25_TSVECTOR_CONFIG = "simple"

# ---------------------------------------------------------------------------
# LegalDocument
# ---------------------------------------------------------------------------

# Status values: ACTIVE | PARTIALLY_AMENDED | INACTIVE | SUPERSEDED
DOC_STATUS_ACTIVE = "ACTIVE"
DOC_STATUS_PARTIALLY_AMENDED = "PARTIALLY_AMENDED"
DOC_STATUS_INACTIVE = "INACTIVE"
DOC_STATUS_SUPERSEDED = "SUPERSEDED"

ALL_DOC_STATUSES = [
    DOC_STATUS_ACTIVE,
    DOC_STATUS_PARTIALLY_AMENDED,
    DOC_STATUS_INACTIVE,
    DOC_STATUS_SUPERSEDED,
]


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    # PK: text, keeps "/" in ID (API must encode when putting into URL)
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # unique=True + index=True => exactly ONE unique index
    # (no extra UNIQUE constraint -> no redundant duplicate index)
    doc_code: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    document_form: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)

    # Enum values (enforced by CHECK constraint)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    # JSONB nullable: amendment info from document_tree.footnotes.
    # none_as_null=True so a Python None becomes SQL NULL instead of JSON 'null'
    # (the JSONB default stores JSON null, which `IS NULL` would not match).
    amended_by: Mapped[dict | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )

    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'PARTIALLY_AMENDED', 'INACTIVE', 'SUPERSEDED')",
            name="ck_legal_documents_status",
        ),
    )


# ---------------------------------------------------------------------------
# LegalChunk
# ---------------------------------------------------------------------------

LEVEL_ARTICLE = "ARTICLE"
LEVEL_CLAUSE = "CLAUSE"
LEVEL_POINT = "POINT"

ALL_CHUNK_LEVELS = [LEVEL_ARTICLE, LEVEL_CLAUSE, LEVEL_POINT]


class LegalChunk(Base):
    __tablename__ = "legal_chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    # FK → legal_documents (enforced)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("legal_documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # TEXT only, NO FK constraint (dangling by design — see V3-ter)
    parent_chunk_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    header_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Separate indexed columns (for B7 filtering) ---
    article_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    clause_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    point_letter: Mapped[str | None] = mapped_column(
        String(16), nullable=True, index=True
    )
    chunk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # --- JSONB: all remaining metadata (audit reads this) ---
    meta: Mapped[dict] = mapped_column(
        JSONB(none_as_null=True), nullable=False, server_default=sa.text("'{}'::jsonb")
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "chunk_level IN ('ARTICLE', 'CLAUSE', 'POINT')",
            name="ck_legal_chunks_chunk_level",
        ),
    )


# ---------------------------------------------------------------------------
# LegalChunkReference
# ---------------------------------------------------------------------------

# needs_reason values
NEEDS_REASON_BOUNDARY = "BOUNDARY"
NEEDS_REASON_UNRESOLVED = "UNRESOLVED"

ALL_NEEDS_REASONS = [NEEDS_REASON_BOUNDARY, NEEDS_REASON_UNRESOLVED]


class LegalChunkReference(Base):
    __tablename__ = "legal_chunk_references"

    # Surrogate PK (target_chunk_id nullable for external refs)
    ref_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK → legal_chunks (enforced, source)
    source_chunk_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("legal_chunks.chunk_id", ondelete="CASCADE"),
        nullable=False,
    )

    # FK → legal_chunks (enforced, target; NULL = external law)
    target_chunk_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("legal_chunks.chunk_id", ondelete="SET NULL"),
        nullable=True,
    )

    target_doc: Mapped[str] = mapped_column(String(128), nullable=False)
    article: Mapped[int] = mapped_column(Integer, nullable=False)
    clause: Mapped[int | None] = mapped_column(Integer, nullable=True)
    point: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rule: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)

    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    needs_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "confidence IN ('HIGH', 'LOW')", name="ck_legal_chunk_references_confidence"
        ),
        CheckConstraint(
            "needs_reason IN ('BOUNDARY', 'UNRESOLVED')",
            name="ck_legal_chunk_references_needs_reason",
        ),
        # ONE UNIQUE constraint, NULLS NOT DISTINCT (PostgreSQL 15+)
        UniqueConstraint(
            "source_chunk_id",
            "target_chunk_id",
            "target_doc",
            "article",
            "clause",
            "point",
            "rule",
            name="uq_legal_chunk_references",
            postgresql_nulls_not_distinct=True,
        ),
        # Reverse index for graph traversal
        Index(
            "ix_legal_chunk_references_target_source",
            "target_chunk_id",
            "source_chunk_id",
            postgresql_nulls_not_distinct=True,
        ),
    )


# ---------------------------------------------------------------------------
# LegalChunkEmbedding  (B6: mistral-embed vectors, B7: hybrid search source)
# ---------------------------------------------------------------------------

# Exact DDL of the generated tsvector, shared with alembic/versions/0003 so a
# drift between model and migration is a visible string diff, not a mystery.
SEARCH_TSV_EXPR = (
    "to_tsvector('simple', coalesce(header_context,'') || ' ' || coalesce(text,''))"
)


class LegalChunkEmbedding(Base):
    """One vector per legal chunk (1024-dim, mistral-embed).

    Separate table instead of a column on ``legal_chunks`` because B5 is
    truncate-and-reseed (``seed_legal.py`` deletes and re-inserts
    ``legal_chunk_references``; chunks are reseeded the same way) while vectors
    are expensive quota (20M TPM team budget). Coupling the two lifetimes would
    throw away paid-for vectors on every reseed. The two ``Vector(1536)``
    columns that already exist (``document_chunks``, ``disciplinary_decisions``)
    belong to the HR Help context and are not reused.
    """

    __tablename__ = "legal_chunk_embeddings"

    # PK is also the FK: one embedding per chunk, cascade-deleted with it.
    chunk_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("legal_chunks.chunk_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # sha256 of legal_chunks.text AT EMBED TIME. Without it, re-running step3
    # or hand-editing a chunk leaves the old vector in the DB and search keeps
    # returning it — wrong, with no signal anywhere. With it, staleness is one
    # SQL statement (verify_embeddings V2) and embed_legal.py can skip safely.
    # CHAR(64): sha256 hex is always exactly 64 chars, so bpchar never stores
    # padding and `=` against a computed sha matches normally.
    content_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)

    model: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)

    # Denormalised copies of legal_chunks (see module docstring). NOT NULL on
    # text, nullable on header_context, mirroring the source table.
    header_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    # BM25 DB-native. A GENERATED column cannot read another table, which is
    # why header_context/text are repeated above rather than joined at query
    # time. 'simple' config = no Vietnamese stemmer (Postgres has none);
    # the plan forbids claiming more than exact-term matching.
    search_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(SEARCH_TSV_EXPR, persisted=True),
        nullable=True,  # GENERATED ALWAYS STORED always yields a value
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        # dimensions must agree with the column type. The 1024 literal is the
        # single-model decision (DECISION 2026-09-26); changing it requires a
        # reviewed migration, same as Vector(1024) itself.
        CheckConstraint(
            f"dimensions = {EMBEDDING_DIM}", name="ck_legal_chunk_embeddings_dimensions"
        ),
        CheckConstraint(
            "model <> ''", name="ck_legal_chunk_embeddings_model_not_empty"
        ),
        # HNSW cosine, same parameters as the HR indexes (one operating
        # standard). Plain CREATE INDEX: 1289 rows, CONCURRENTLY is pointless.
        Index(
            "ix_legal_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # GIN for the tsvector BM25 path
        Index(
            "ix_legal_chunk_embeddings_search_tsv",
            "search_tsv",
            postgresql_using="gin",
        ),
    )
