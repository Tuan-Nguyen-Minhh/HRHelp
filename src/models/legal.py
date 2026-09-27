"""SQLAlchemy models for legal documents, chunks, and cross-references.

B4: documents + chunks (metadata & effectiveness)
B5: chunk_references (cross-reference graph)

All tables have created_at/updated_at. parent_chunk_id is TEXT with NO FK
constraint (dangling values exist by design — see V3-ter).

Two column decisions that are easy to get wrong:

* `parent_chunk_id` deliberately has no ForeignKey. Every non-null value in the
  current dataset dangles (0 resolve), which is inherited from step3's
  chunking design. Adding an FK would make the seed impossible to run.
* The JSONB columns use `none_as_null=True`. SQLAlchemy's default serialises a
  Python None as JSON `null`, which is *not* SQL NULL — so `amended_by IS NULL`
  would silently not match the two documents that have no footnotes.
"""
from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

# ---------------------------------------------------------------------------
# Document
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


class Document(Base):
    __tablename__ = "documents"

    # PK: text, keeps "/" in ID (API must encode when putting into URL)
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # unique=True + index=True => exactly ONE unique index named ix_documents_doc_code
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
            name="ck_documents_status",
        ),
    )


# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------

LEVEL_ARTICLE = "ARTICLE"
LEVEL_CLAUSE = "CLAUSE"
LEVEL_POINT = "POINT"

ALL_CHUNK_LEVELS = [LEVEL_ARTICLE, LEVEL_CLAUSE, LEVEL_POINT]


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    # FK → documents (enforced)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
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
            name="ck_chunks_chunk_level",
        ),
    )


# ---------------------------------------------------------------------------
# ChunkReference
# ---------------------------------------------------------------------------

# needs_reason values
NEEDS_REASON_BOUNDARY = "BOUNDARY"
NEEDS_REASON_UNRESOLVED = "UNRESOLVED"

ALL_NEEDS_REASONS = [NEEDS_REASON_BOUNDARY, NEEDS_REASON_UNRESOLVED]


class ChunkReference(Base):
    __tablename__ = "chunk_references"

    # Surrogate PK (target_chunk_id nullable for external refs)
    ref_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK → chunks (enforced, source)
    source_chunk_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("chunks.chunk_id", ondelete="CASCADE"),
        nullable=False,
    )

    # FK → chunks (enforced, target; NULL = external law)
    target_chunk_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("chunks.chunk_id", ondelete="SET NULL"),
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
            "confidence IN ('HIGH', 'LOW')", name="ck_chunk_references_confidence"
        ),
        CheckConstraint(
            "needs_reason IN ('BOUNDARY', 'UNRESOLVED')",
            name="ck_chunk_references_needs_reason",
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
            name="uq_chunk_references",
            postgresql_nulls_not_distinct=True,
        ),
        # Reverse index for graph traversal
        Index(
            "ix_chunk_references_target_source",
            "target_chunk_id",
            "source_chunk_id",
            postgresql_nulls_not_distinct=True,
        ),
    )
