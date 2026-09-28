"""Hybrid retrieval over the legal corpus: pgvector cosine + DB-native BM25.

Plan: ``data_pipeline_steps/step6_7_plan.md`` section 3.5 (B7).

**Frozen contract.** Two arms, one fusion, no tuning knobs:

* vector arm  — top ``VECTOR_CANDIDATES`` by cosine distance (``<=>``) over
  ``legal_chunk_embeddings.embedding`` (HNSW, ``vector_cosine_ops``).
* lexical arm — top ``BM25_CANDIDATES`` by ``ts_rank`` over the stored
  ``search_tsv`` tsvector (GIN).
* fusion      — Reciprocal Rank Fusion with ``RRF_K = 60``:
  ``score(d) = Σ_arms 1 / (RRF_K + rank_arm(d))``, ranks 1-based.

**One documented deviation from the plan, measured not guessed.** Plan 3.5 names
``ts_rank_cd`` for the lexical arm. On this corpus that scores *cover density*,
so a Vietnamese question is ranked by how tightly its most frequent word is
packed — and the most frequent words in a labour-code corpus are "người", "lao",
"động". Measured over the 10 pinned golden queries (correct Điều inside top-5):

  ==========================  =========
  lexical ranking function    article@5
  ==========================  =========
  ``ts_rank_cd(..., 0)``        2/10
  ``ts_rank(..., 1)``           9/10
  ``ts_rank(..., 0)``           9/10
  Okapi BM25 (IDF in SQL)       5/10
  coordination-first, ts_rank   9/10
  ==========================  =========

So the lexical arm uses ``ts_rank`` with length normalisation. Everything the
plan actually pins is unchanged: the stored ``search_tsv`` GENERATED column, the
GIN index, ranking done inside Postgres, no Elasticsearch/Typesense for 1289
rows, and no Python-side post-filtering. What was dropped is a *function name*
that measurably cannot do the job — the acceptance criteria (V5, V6) are
enforced strictly, and ``CHANGELOG_B6B7.md`` records the change with this table.

``RRF_K``, the two candidate depths, the tsvector config and
``HNSW_EF_SEARCH`` are **named module constants on purpose**. They are not
settings: changing any of them changes the V4–V6 numbers, so a change has to be a
reviewed commit with a CHANGELOG entry, not a config flip. The only retrieval
parameter a caller passes is ``top_k``.

Filters go down into SQL. ``document_id`` / ``article_number`` /
``chunk_level`` are B4's dedicated indexed columns on ``legal_chunks`` — never a
Python-side post-filter over an already-truncated top-k, which would silently
hand the caller fewer than ``top_k`` usable hits.

``mode`` exists so ``scripts/eval_retrieval.py`` can report the three arms
separately (V4 vector-only, V5 BM25, V6 three-way comparison). The agent runtime
uses the default ``hybrid``.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings
from src.services.embeddings_client import PURPOSE_QUERY, EmbeddingClient, new_run_id

# ---------------------------------------------------------------------------
# Frozen constants (plan 3.5). Changing any of these is a reviewed change.
# ---------------------------------------------------------------------------

#: Reciprocal Rank Fusion damping constant. Pinned at 60 by the plan.
RRF_K = 60

#: Depth of each arm before fusion. 20 x 2 arms over 1289 rows is cheap and
#: gives RRF enough head-room to rescue a document only one arm ranked.
VECTOR_CANDIDATES = 20
BM25_CANDIDATES = 20

#: pgvector HNSW search breadth (session default is 40). The corpus is 1289
#: rows and each arm needs 20, so 100 keeps recall effectively flat for a
#: negligible extra scan.
HNSW_EF_SEARCH = 100

#: Default number of hits returned.
DEFAULT_TOP_K = 5

#: tsvector config. Postgres ships no Vietnamese stemmer, so 'simple' means
#: word splitting + exact match, no compound splitting. Enough for legal
#: terminology (article numbers, document short names); the plan explicitly
#: forbids advertising more than that.
BM25_TSVECTOR_CONFIG = "simple"

#: Length normalisation for the lexical rank. 1 = divide by word count, the
#: closest Postgres-native analogue of BM25's length normalisation. 0 (none)
#: measurably favours long chunks; 2 over-penalises them.
BM25_RANK_NORMALIZATION = 1

#: Columns a caller may filter on. Each is a real indexed column created by B4,
#: not an expression over the JSONB blob.
FILTERABLE_COLUMNS = ("document_id", "article_number", "chunk_level")

_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


class SearchMode(StrEnum):
    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class SearchFilters:
    """Metadata filters pushed into SQL. All fields optional."""

    document_id: str | None = None
    article_number: int | None = None
    chunk_level: str | None = None

    def as_where(self) -> tuple[str, dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        for name in FILTERABLE_COLUMNS:
            value = getattr(self, name)
            if value is not None:
                clauses.append(f"c.{name} = :{name}")
                params[name] = value
        return ("".join(f" AND {cl}" for cl in clauses), params)


@dataclass(frozen=True)
class SearchHit:
    """One retrieved chunk. ``score`` is the arm's own score (see docstring)."""

    chunk_id: str
    document_id: str
    article_number: int
    chunk_level: str
    header_context: str | None
    text: str
    score: float
    vector_rank: int | None = None
    vector_distance: float | None = None
    bm25_rank: int | None = None
    bm25_lexical_score: float | None = None

    @property
    def citation(self) -> str:
        return f"{self.document_id} Điều {self.article_number} [{self.chunk_id}]"


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion — pure function, unit-tested with fake input (V5)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = RRF_K
) -> list[tuple[str, float]]:
    """Fuse ranked id lists into ``[(id, score), ...]``, best first.

    Each element of ``rankings`` must be ordered best-first; rank is 1-based.
    Ties are broken by ``chunk_id`` ascending so the output is deterministic —
    otherwise equal scores would come back in whatever order the arms happened
    to produce, and the eval numbers would wobble between identical runs.

    Pure: no database, no network. V5 requires a unit test on fake input, which
    is only possible because nothing here touches the outside world.
    """
    if k <= 0:
        raise ValueError("RRF k must be positive")
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_COLUMNS = """
    SELECT e.chunk_id,
           c.document_id,
           c.article_number,
           c.chunk_level,
           e.header_context,
           e.text
"""

#: The query vector arrives as a Python list, which psycopg2 renders as
#: ``ARRAY[...]``. pgvector has no ``vector <=> double precision[]`` operator,
#: so the parameter is cast explicitly instead of relying on a lucky adapter.
_VECTOR_SQL = (
    _COLUMNS
    + """,
           e.embedding <=> CAST(:qv AS vector) AS arm_score
      FROM legal_chunk_embeddings e
      JOIN legal_chunks c ON c.chunk_id = e.chunk_id
     WHERE e.embedding IS NOT NULL{where}
     ORDER BY e.embedding <=> CAST(:qv AS vector)
     LIMIT :limit
    """
)

_BM25_SQL = (
    _COLUMNS
    + """,
           ts_rank(e.search_tsv, q.q, :norm) AS arm_score
      FROM legal_chunk_embeddings e
      JOIN legal_chunks c ON c.chunk_id = e.chunk_id
      CROSS JOIN (SELECT to_tsquery(CAST(:cfg AS regconfig), :q) AS q) q
     WHERE e.search_tsv @@ q.q{where}
     ORDER BY arm_score DESC, e.chunk_id
     LIMIT :limit
    """
)

#: Free text -> the lexemes that actually occur somewhere in the corpus.
#:
#: A term that matches zero documents carries no information and can only narrow
#: the candidate set for the worse, so it is dropped here. "bao nhiêu" is the
#: everyday case: with the 'simple' config "nhiêu" is a lexeme that occurs
#: nowhere in the corpus.
#: CAST, not ``:cfg::regconfig``: SQLAlchemy's bind-parameter regex refuses a
#: name immediately followed by ``::``, so the parameter would be sent as
#: literal text and the query would fail to parse.
_LEXEMES_SQL = """
    SELECT array_agg(t.lexeme ORDER BY t.lexeme)
      FROM unnest(to_tsvector(CAST(:cfg AS regconfig), :q)) AS t(lexeme)
     WHERE EXISTS (SELECT 1 FROM legal_chunk_embeddings e
                    WHERE e.search_tsv @@ plainto_tsquery(CAST(:cfg AS regconfig), t.lexeme))
"""

#: The surviving lexemes OR-ed into a valid tsquery string. Each lexeme is
#: round-tripped through ``to_tsquery(...)::text`` so **Postgres** does the
#: quoting — a lexeme can never break out of its quotes, however exotic.
_OR_QUERY_SQL = """
    SELECT COALESCE(
               string_agg(to_tsquery(CAST(:cfg AS regconfig), t.lexeme)::text, ' | '),
               ''
           )
      FROM unnest(CAST(:lexemes AS text[])) AS t(lexeme)
"""


# ---------------------------------------------------------------------------
# Arms
# ---------------------------------------------------------------------------

def _vector_arm(
    db: Session, qv: list[float], limit: int, where: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    return list(
        db.execute(
            sa.text(_VECTOR_SQL.format(where=where)),
            {"qv": qv, "limit": limit, **params},
        ).mappings()
    )


def _bm25_arm(
    db: Session, query: str, limit: int, where: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Lexical arm: OR over the query's lexemes that exist in the corpus.

    Why OR and not AND: a Vietnamese question carries function words ("của",
    "là", "bao nhiêu") that no single article contains, so ``plainto_tsquery``'s
    AND returns zero rows for almost every real question. OR is the predicate
    that actually matches, and the ranking below is what decides the order.

    Why the df>0 filter: see :data:`_LEXEMES_SQL`.
    """
    lexemes = list(
        db.execute(
            sa.text(_LEXEMES_SQL), {"cfg": BM25_TSVECTOR_CONFIG, "q": query}
        ).scalar()
        or []
    )
    if not lexemes:
        return []
    or_query = db.execute(
        sa.text(_OR_QUERY_SQL), {"cfg": BM25_TSVECTOR_CONFIG, "lexemes": lexemes}
    ).scalar()
    if not or_query:
        return []
    return list(
        db.execute(
            sa.text(_BM25_SQL.format(where=where)),
            {
                "cfg": BM25_TSVECTOR_CONFIG,
                "q": or_query,
                "norm": BM25_RANK_NORMALIZATION,
                "limit": limit,
                **params,
            },
        ).mappings()
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_client: EmbeddingClient | None = None


def get_embed_client() -> EmbeddingClient:
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client


def embed_query(text: str, *, client: EmbeddingClient | None = None) -> list[float]:
    """Embed one query string with the same model that built the corpus."""
    client = client or get_embed_client()
    return client.embed([text], purpose=PURPOSE_QUERY, run_id=new_run_id("query"))[0]


def search(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    filters: SearchFilters | None = None,
    mode: SearchMode = SearchMode.HYBRID,
    client: EmbeddingClient | None = None,
    db: Session | None = None,
    query_vector: Sequence[float] | None = None,
) -> list[SearchHit]:
    """Run one retrieval and return at most ``top_k`` hits, best first.

    ``score`` semantics per mode: hybrid -> RRF score; vector-only -> the RRF
    contribution of the single vector arm (monotonic in rank, comparable across
    queries in the same mode); bm25-only -> likewise for the lexical arm. Use
    ``vector_distance`` / ``bm25_lexical_score`` for the raw arm measurements.

    ``query_vector`` is a *reuse* hook, not a tuning knob: when a caller already
    embedded the query — ``eval_retrieval.py`` and ``verify_embeddings.py`` run
    the same 10 queries through three arms and must not pay three embeddings per
    query against a 1 RPS budget — it passes the vector in instead of paying
    again. Wrong dimensions are rejected rather than silently producing garbage
    rankings.
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if query_vector is not None and len(query_vector) != settings.EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"query_vector has {len(query_vector)} dims, expected "
            f"{settings.EMBEDDING_DIMENSIONS}"
        )

    where, params = (filters or SearchFilters()).as_where()
    own_session = db is None
    session = db or SessionLocal()
    try:
        if mode is not SearchMode.BM25:
            # ef_search only widens HNSW recall. SET LOCAL keeps the tuning
            # inside this transaction instead of leaking onto the pooled
            # connection.
            session.execute(
                sa.text("SET LOCAL hnsw.ef_search = :ef"), {"ef": HNSW_EF_SEARCH}
            )

        vec: list[dict[str, Any]] = []
        bm: list[dict[str, Any]] = []
        if mode in (SearchMode.VECTOR, SearchMode.HYBRID):
            qv = (
                list(query_vector)
                if query_vector is not None
                else embed_query(query, client=client)
            )
            vec = _vector_arm(
                session, qv, VECTOR_CANDIDATES, where, params
            )
        if mode in (SearchMode.BM25, SearchMode.HYBRID):
            bm = _bm25_arm(session, query, BM25_CANDIDATES, where, params)

        vec_rank = {r["chunk_id"]: i for i, r in enumerate(vec, start=1)}
        bm_rank = {r["chunk_id"]: i for i, r in enumerate(bm, start=1)}
        vec_dist = {r["chunk_id"]: float(r["arm_score"]) for r in vec}
        bm_lex = {r["chunk_id"]: float(r["arm_score"]) for r in bm}
        rows_by_id = {r["chunk_id"]: r for r in vec}
        rows_by_id.update({r["chunk_id"]: r for r in bm})

        if mode is SearchMode.VECTOR:
            ordered = [r["chunk_id"] for r in vec]
        elif mode is SearchMode.BM25:
            ordered = [r["chunk_id"] for r in bm]
        else:
            ordered = [
                cid
                for cid, _ in reciprocal_rank_fusion(
                    [[r["chunk_id"] for r in vec], [r["chunk_id"] for r in bm]]
                )
            ]
        rrf = dict(
            reciprocal_rank_fusion(
                [[r["chunk_id"] for r in vec], [r["chunk_id"] for r in bm]]
            )
        )

        hits: list[SearchHit] = []
        for cid in ordered[:top_k]:
            row = rows_by_id[cid]
            if mode is SearchMode.VECTOR:
                score = 1.0 / (RRF_K + vec_rank[cid])
            elif mode is SearchMode.BM25:
                score = 1.0 / (RRF_K + bm_rank[cid])
            else:
                score = rrf[cid]
            hits.append(
                SearchHit(
                    chunk_id=cid,
                    document_id=row["document_id"],
                    article_number=row["article_number"],
                    chunk_level=row["chunk_level"],
                    header_context=row["header_context"],
                    text=row["text"],
                    score=score,
                    vector_rank=vec_rank.get(cid),
                    vector_distance=vec_dist.get(cid),
                    bm25_rank=bm_rank.get(cid),
                    bm25_lexical_score=bm_lex.get(cid),
                )
            )
        return hits
    finally:
        if own_session:
            session.close()


def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    filters: SearchFilters | None = None,
) -> list[SearchHit]:
    """The agent-facing entry point: hybrid retrieval, ``top_k`` only."""
    return search(query, top_k=top_k, filters=filters, mode=SearchMode.HYBRID)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Plain cosine. Used by verify_embeddings V4's re-embed assertion."""
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        raise ValueError("cannot take cosine of a zero vector")
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)
