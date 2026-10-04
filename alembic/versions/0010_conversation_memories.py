"""Add short-term conversation memories.

Revision ID: 0010_conversation_memories
Revises: 0009_assessment_form
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_conversation_memories"
down_revision: str | Sequence[str] | None = "0009_assessment_form"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("open_questions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("pending_fact_keys", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("last_user_intent", sa.String(length=80), nullable=True),
        sa.Column("pending_action", sa.String(length=80), nullable=True),
        sa.Column("recent_messages", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_conversation_memories_conversation_id", "conversation_memories", ["conversation_id"], unique=True)
    op.create_index("idx_conversation_memories_pending_action", "conversation_memories", ["pending_action"])


def downgrade() -> None:
    op.drop_index("idx_conversation_memories_pending_action", table_name="conversation_memories")
    op.drop_index("uq_conversation_memories_conversation_id", table_name="conversation_memories")
    op.drop_table("conversation_memories")
