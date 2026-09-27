"""B4+B5: create documents, chunks, chunk_references

Revision ID: 0001_legal_schema
Revises:
Create Date: 2026-09-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_legal_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
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
            name="ck_documents_status",
        ),
    )
    # SINGLE unique index on doc_code (no redundant UNIQUE constraint)
    op.create_index("ix_documents_doc_code", "documents", ["doc_code"], unique=True)

    # ------------------------------------------------------------------
    # chunks
    # ------------------------------------------------------------------
    op.create_table(
        "chunks",
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
            ["documents.document_id"],
            ondelete="CASCADE",
            name="fk_chunks_document_id",
        ),
        sa.CheckConstraint(
            "chunk_level IN ('ARTICLE', 'CLAUSE', 'POINT')",
            name="ck_chunks_chunk_level",
        ),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_article_number", "chunks", ["article_number"])
    op.create_index("ix_chunks_clause_number", "chunks", ["clause_number"])
    op.create_index("ix_chunks_point_letter", "chunks", ["point_letter"])
    op.create_index("ix_chunks_chunk_level", "chunks", ["chunk_level"])

    # ------------------------------------------------------------------
    # chunk_references
    # ------------------------------------------------------------------
    op.create_table(
        "chunk_references",
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
            ["chunks.chunk_id"],
            ondelete="CASCADE",
            name="fk_chunk_references_source_chunk_id",
        ),
        sa.ForeignKeyConstraint(
            ["target_chunk_id"],
            ["chunks.chunk_id"],
            ondelete="SET NULL",
            name="fk_chunk_references_target_chunk_id",
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH', 'LOW')", name="ck_chunk_references_confidence"
        ),
        sa.CheckConstraint(
            "needs_reason IN ('BOUNDARY', 'UNRESOLVED')",
            name="ck_chunk_references_needs_reason",
        ),
        sa.UniqueConstraint(
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
    )
    # Reverse index for graph traversal
    op.create_index(
        "ix_chunk_references_target_source",
        "chunk_references",
        ["target_chunk_id", "source_chunk_id"],
        unique=False,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_references_target_source", table_name="chunk_references")
    op.drop_table("chunk_references")

    op.drop_index("ix_chunks_chunk_level", table_name="chunks")
    op.drop_index("ix_chunks_point_letter", table_name="chunks")
    op.drop_index("ix_chunks_clause_number", table_name="chunks")
    op.drop_index("ix_chunks_article_number", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("ix_documents_doc_code", table_name="documents")
    op.drop_table("documents")
