"""B6/B7: legal_chunk_embeddings (mistral-embed vectors + BM25 tsvector).

Revision ID: 0003_legal_embeddings
Revises: 0002_unify_mistral_embed
Create Date: 2026-09-28

Plan: data_pipeline_steps/step6_7_plan.md REV.1, section 3.4.

Three decisions worth stating before the DDL:

1. **A new table, not a column on ``legal_chunks``.** B5 reseeds with
   DELETE + INSERT; vectors are paid-for quota (20M TPM team budget). Sharing a
   lifecycle would discard every vector on each reseed. The two existing
   ``Vector(1024)`` columns (``document_chunks``, ``disciplinary_decisions``)
   belong to the HR Help bounded context and are deliberately not reused.

2. **``content_sha256`` is NOT NULL.** It is the sha256 of
   ``legal_chunks.text`` at embed time. Without it, a re-run of step3 or a
   hand edit leaves a stale vector that search still returns — wrong, silently.
   With it, staleness is one SQL statement and ``embed_legal.py`` can resume
   without wasting quota.

3. **``header_context`` / ``text`` are repeated on purpose.** The plan puts the
   BM25 ``search_tsv`` generated column on the embeddings table ("chung với tạo
   bảng"), but a PostgreSQL GENERATED column can only read columns of its own
   table. The alternatives were to add the column to ``legal_chunks`` (i.e.
   modify a B4 table, which plan section 0 forbids) or to build the tsvector
   per query in SQL (which cannot use a GIN index). Repeating the two text
   columns keeps ``legal_chunks`` byte-identical to the B4/B5 output while
   still allowing a stored, indexed tsvector. The copies are protected by
   ``ON DELETE CASCADE`` and are asserted byte-equal to the originals by
   ``scripts/verify_embeddings.py`` V2, so they cannot silently drift.

The 1024-dim literal and the 'simple' tsvector config are the single-model
decision of 2026-09-26 (see DECISION in 0002). They are written as literals
here on purpose: a migration must stay readable and reproducible without
importing application code.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_legal_embeddings"
down_revision: str | Sequence[str] | None = "0002_unify_mistral_embed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024
EMBEDDING_MODEL = "mistral-embed"

# Must stay byte-identical to SEARCH_TSV_EXPR in src/models/legal.py.
SEARCH_TSV_EXPR = (
    "to_tsvector('simple', coalesce(header_context,'') || ' ' || coalesce(text,''))"
)

TABLE = "legal_chunk_embeddings"
IDX_HNSW = "ix_legal_embeddings_hnsw"
IDX_TSV_GIN = "ix_legal_chunk_embeddings_search_tsv"


def upgrade() -> None:
    op.create_table(
        TABLE,
        # PK doubles as the FK: one embedding per chunk, removed with the chunk.
        sa.Column(
            "chunk_id",
            sa.String(128),
            sa.ForeignKey("legal_chunks.chunk_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        # CHAR(64) because a sha256 hex digest is always exactly 64 characters,
        # so bpchar never stores padding and `=` behaves like varchar.
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        # Denormalised from legal_chunks — see the module docstring, reason 3.
        sa.Column("header_context", sa.Text, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR,
            sa.Computed(SEARCH_TSV_EXPR, persisted=True),
            nullable=True,
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
        sa.CheckConstraint(
            f"dimensions = {EMBEDDING_DIM}", name="ck_legal_chunk_embeddings_dimensions"
        ),
        sa.CheckConstraint(
            "model <> ''", name="ck_legal_chunk_embeddings_model_not_empty"
        ),
    )

    # HNSW cosine. m=16 / ef_construction=64 are the same values the HR indexes
    # use (see 0002), so there is one operating standard to tune and document.
    # 1289 rows: a plain CREATE INDEX is enough, CONCURRENTLY buys nothing and
    # cannot run inside a transaction block anyway.
    op.execute(
        sa.text(
            f"CREATE INDEX {IDX_HNSW} ON {TABLE} "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
    )
    # GIN for the DB-native BM25 path. 'simple' config: Postgres has no
    # Vietnamese stemmer, so this is word splitting + exact match. Documented
    # limitation, not a bug.
    op.execute(
        sa.text(f"CREATE INDEX {IDX_TSV_GIN} ON {TABLE} USING gin (search_tsv)")
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_TSV_GIN}"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_HNSW}"))
    op.drop_table(TABLE)
