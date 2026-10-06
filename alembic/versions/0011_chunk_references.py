"""Add chunk_references: cross-reference graph on the live corpus.

Revision ID: 0011_chunk_references
Revises: 0010_conversation_memories
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_chunk_references"
down_revision: str | Sequence[str] | None = "0010_conversation_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Purely additive: one new table. No existing table is read or rewritten.

    The FK targets are the two ON DELETE behaviours the runtime depends on —
    CASCADE on the source (a citation without a source is meaningless) and SET
    NULL on the target (losing a chunk must not erase the fact that something
    cited it, so the edge degrades to an external reference instead).
    """
    op.create_table(
        "chunk_references",
        sa.Column("ref_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_doc", sa.String(length=128), nullable=False),
        sa.Column("article", sa.Integer(), nullable=False),
        sa.Column("clause", sa.Integer(), nullable=True),
        sa.Column("point", sa.String(length=16), nullable=True),
        sa.Column("rule", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("needs_reason", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("confidence IN ('HIGH', 'LOW')", name="ck_chunk_references_confidence"),
        sa.CheckConstraint(
            "needs_reason IN ('BOUNDARY', 'UNRESOLVED')",
            name="ck_chunk_references_needs_reason",
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"],
            ["document_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_chunk_id"],
            ["document_chunks.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("ref_id"),
    )

    # Leading column is source_chunk_id, so the unique key doubles as the index
    # for outgoing traversal. NULLS NOT DISTINCT stops two rows that differ only
    # in whether clause/point is NULL from both being admitted.
    op.create_index(
        "uq_chunk_references",
        "chunk_references",
        [
            "source_chunk_id",
            "target_chunk_id",
            "target_doc",
            "article",
            "clause",
            "point",
            "rule",
        ],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    # Reverse traversal: "which chunks cite article N of document D".
    op.create_index(
        "ix_chunk_references_target_source",
        "chunk_references",
        ["target_chunk_id", "source_chunk_id"],
    )


def downgrade() -> None:
    """Drops the table. Nothing else in the schema references it."""
    op.drop_index("ix_chunk_references_target_source", table_name="chunk_references")
    op.drop_index("uq_chunk_references", table_name="chunk_references")
    op.drop_table("chunk_references")
