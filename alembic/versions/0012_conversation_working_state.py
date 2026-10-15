"""Persist the shared conversation schema without changing existing facts.

Revision ID: 0012_conversation_working_state
Revises: 0011_chunk_references
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_conversation_working_state"
down_revision = "0011_chunk_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_memories",
        sa.Column("working_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("conversation_memories", "working_state")
