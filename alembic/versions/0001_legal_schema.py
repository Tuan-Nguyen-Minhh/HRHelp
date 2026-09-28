"""B4+B5: create legal_documents, legal_chunks, legal_chunk_references.

Revision ID: 0001_legal_schema
Revises: 04e5c85e7957
Create Date: 2026-09-27

Table-naming note (2026-09-28): the legal corpus tables were first created as
``documents`` / ``chunks`` / ``chunk_references``, which collide with the HR
Help bounded context on ``main`` (``documents`` + ``document_chunks``,
migration ``04e5c85e7957``). Two heads, one duplicated table name, and two
Python classes both called ``Document``. The legal tables were renamed to the
``legal_`` prefix *before this branch merged*, so no production database ever
saw the old names — the handoff dump was regenerated from the JSON sources.
This revision is therefore written directly with the final names instead of a
CREATE-then-RENAME pair, and it chains after ``04e5c85e7957`` so ``alembic
heads`` reports a single head.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_legal_schema"
down_revision: str | Sequence[str] | None = "04e5c85e7957"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # legal_documents
    # ------------------------------------------------------------------
    op.create_table(
        "legal_documents",
        sa.Column("document_id", sa.String(64), primary_key=True),
        sa.Column("doc_code", sa.String(32), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("document_form", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("amended_by", postgresql.JSONB, nullable=True),
        sa.Column("article_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PARTIALLY_AMENDED', 'INACTIVE', 'SUPERSEDED')",
            name="ck_legal_documents_status",
        ),
    )
    # SINGLE unique index on doc_code (no redundant UNIQUE constraint)
    op.create_index(
        "ix_legal_documents_doc_code", "legal_documents", ["doc_code"], unique=True
    )

    # ------------------------------------------------------------------
    # legal_chunks
    # ------------------------------------------------------------------
    op.create_table(
        "legal_chunks",
        sa.Column("chunk_id", sa.String(128), primary_key=True),
        sa.Column("document_id", sa.String(64), nullable=False),
        # TEXT, NO FK constraint on purpose (dangling values by design)
        sa.Column("parent_chunk_id", sa.String(128), nullable=True),
        sa.Column("header_context", sa.Text, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("article_number", sa.Integer, nullable=False),
        sa.Column("clause_number", sa.Integer, nullable=True),
        sa.Column("point_letter", sa.String(16), nullable=True),
        sa.Column("chunk_level", sa.String(16), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["legal_documents.document_id"],
            ondelete="CASCADE",
            name="fk_legal_chunks_document_id",
        ),
        sa.CheckConstraint(
            "chunk_level IN ('ARTICLE', 'CLAUSE', 'POINT')",
            name="ck_legal_chunks_chunk_level",
        ),
    )
    op.create_index("ix_legal_chunks_document_id", "legal_chunks", ["document_id"])
    op.create_index(
        "ix_legal_chunks_article_number", "legal_chunks", ["article_number"]
    )
    op.create_index(
        "ix_legal_chunks_clause_number", "legal_chunks", ["clause_number"]
    )
    op.create_index(
        "ix_legal_chunks_point_letter", "legal_chunks", ["point_letter"]
    )
    op.create_index("ix_legal_chunks_chunk_level", "legal_chunks", ["chunk_level"])

    # ------------------------------------------------------------------
    # legal_chunk_references
    # ------------------------------------------------------------------
    op.create_table(
        "legal_chunk_references",
        sa.Column("ref_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_chunk_id", sa.String(128), nullable=False),
        sa.Column("target_chunk_id", sa.String(128), nullable=True),
        sa.Column("target_doc", sa.String(128), nullable=False),
        sa.Column("article", sa.Integer, nullable=False),
        sa.Column("clause", sa.Integer, nullable=True),
        sa.Column("point", sa.String(16), nullable=True),
        sa.Column("rule", sa.String(64), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column(
            "needs_review",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("needs_reason", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"],
            ["legal_chunks.chunk_id"],
            ondelete="CASCADE",
            name="fk_legal_chunk_references_source_chunk_id",
        ),
        sa.ForeignKeyConstraint(
            ["target_chunk_id"],
            ["legal_chunks.chunk_id"],
            ondelete="SET NULL",
            name="fk_legal_chunk_references_target_chunk_id",
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'LOW')",
            name="ck_legal_chunk_references_confidence",
        ),
        sa.CheckConstraint(
            "needs_reason IN ('BOUNDARY', 'UNRESOLVED')",
            name="ck_legal_chunk_references_needs_reason",
        ),
        sa.UniqueConstraint(
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
    )
    # Reverse index for graph traversal
    op.create_index(
        "ix_legal_chunk_references_target_source",
        "legal_chunk_references",
        ["target_chunk_id", "source_chunk_id"],
        unique=False,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legal_chunk_references_target_source",
        table_name="legal_chunk_references",
    )
    op.drop_table("legal_chunk_references")

    op.drop_index("ix_legal_chunks_chunk_level", table_name="legal_chunks")
    op.drop_index("ix_legal_chunks_point_letter", table_name="legal_chunks")
    op.drop_index("ix_legal_chunks_clause_number", table_name="legal_chunks")
    op.drop_index("ix_legal_chunks_article_number", table_name="legal_chunks")
    op.drop_index("ix_legal_chunks_document_id", table_name="legal_chunks")
    op.drop_table("legal_chunks")

    op.drop_index("ix_legal_documents_doc_code", table_name="legal_documents")
    op.drop_table("legal_documents")
