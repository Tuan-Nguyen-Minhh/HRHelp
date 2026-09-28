"""Unify all embeddings on mistral-embed (1024-dim).

Revision ID: 0002_unify_mistral_embed
Revises: 0001_legal_schema
Create Date: 2026-09-28

DECISION 2026-09-26, P-029: one embedding model for the whole database,
mistral-embed (1024-dim). The two Vector(1536) columns came from the OpenAI
template (text-embedding-3-small); no code in the repo ever wrote them —
MistralAIEmbeddings in src/services/vector_store.py is the only embedding
runtime — and no environment holds vectors yet (both columns are empty on dev;
staging/prod must confirm before upgrading).

The migration refuses to run when non-null embeddings exist instead of
silently truncating 1536-dim vectors into 1024 dims: old vectors would become
garbage that still gets returned by search. If it fires, re-embed from source
text with mistral-embed first, then re-run.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_unify_mistral_embed"
down_revision: str | Sequence[str] | None = "0001_legal_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGETS: tuple[tuple[str, str, str], ...] = (
    (
        "document_chunks",
        "idx_document_chunks_embedding_hnsw",
        "embedding IS NOT NULL",
    ),
    (
        "disciplinary_decisions",
        "idx_disciplinary_decisions_embedding_hnsw",
        "is_precedent AND embedding IS NOT NULL",
    ),
)


def upgrade() -> None:
    conn = op.get_bind()
    for table, index, _ in TARGETS:
        n = conn.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE embedding IS NOT NULL")
        ).scalar()
        if n:
            raise RuntimeError(
                f"{table} holds {n} embedded rows in 1536 dims. Re-embed them "
                "with mistral-embed (1024-dim) first — this migration will not "
                "truncate vectors into garbage."
            )
    for table, index, where in TARGETS:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index}"))
        op.alter_column(
            table,
            "embedding",
            existing_type=Vector(1536),
            type_=Vector(1024),
        )
        op.execute(
            sa.text(
                f"CREATE INDEX {index} ON {table} "
                "USING hnsw (embedding vector_cosine_ops) "
                f"WITH (m = 16, ef_construction = 64) WHERE {where}"
            )
        )


def downgrade() -> None:
    for table, index, where in TARGETS:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index}"))
        op.alter_column(
            table,
            "embedding",
            existing_type=Vector(1024),
            type_=Vector(1536),
        )
        op.execute(
            sa.text(
                f"CREATE INDEX {index} ON {table} "
                "USING hnsw (embedding vector_cosine_ops) "
                f"WITH (m = 16, ef_construction = 64) WHERE {where}"
            )
        )
