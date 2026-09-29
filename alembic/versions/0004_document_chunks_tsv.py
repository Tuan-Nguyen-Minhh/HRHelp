"""Add search_tsv generated column + GIN index to document_chunks.

Revision ID: 0004_document_chunks_tsv
Revises: 0003_legal_embeddings
Create Date: 2026-09-29

Bridges the BM25 capability from legal_chunk_embeddings into document_chunks
so that cite and hybrid_search can use full-text search on the HR tables
after the legal→HR data migration (seed_hr_from_legal.py).

The expression mirrors the legal_chunk_embeddings approach: ``'simple'``
config (no Vietnamese stemmer), stored + GIN-indexed for O(1) query.
Uses section_title (header breadcrumb) + content as the tsvector source,
which is the HR equivalent of header_context || text on the legal side.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_document_chunks_tsv"
down_revision: str | Sequence[str] | None = "0003_legal_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "document_chunks"
TSV_COLUMN = "search_tsv"
IDX_GIN = "ix_document_chunks_search_tsv"

# Same 'simple' config as legal_chunk_embeddings (no Vietnamese stemmer).
SEARCH_TSV_EXPR = (
    "to_tsvector('simple', coalesce(section_title,'') || ' ' || coalesce(content,''))"
)


def upgrade() -> None:
    # Widen section_title from VARCHAR(255) to TEXT — legal breadcrumbs
    # (header_context) routinely exceed 255 characters.
    op.execute(
        sa.text(f"ALTER TABLE {TABLE} ALTER COLUMN section_title TYPE TEXT")
    )

    # Add generated tsvector column
    op.execute(
        sa.text(
            f"ALTER TABLE {TABLE} "
            f"ADD COLUMN {TSV_COLUMN} tsvector "
            f"GENERATED ALWAYS AS ({SEARCH_TSV_EXPR}) STORED"
        )
    )
    # GIN index for BM25
    op.execute(
        sa.text(f"CREATE INDEX {IDX_GIN} ON {TABLE} USING gin ({TSV_COLUMN})")
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_GIN}"))
    op.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS {TSV_COLUMN}"))
    op.execute(
        sa.text(f"ALTER TABLE {TABLE} ALTER COLUMN section_title TYPE VARCHAR(255)")
    )
