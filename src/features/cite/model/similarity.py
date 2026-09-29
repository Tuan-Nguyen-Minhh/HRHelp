"""Vector retriever over ``document_chunks.embedding``.

The column is mistral-embed, ``settings.EMBEDDING_DIMENSIONS`` wide (1024).
A query that arrives without a vector is embedded here. A missing API key, a
failed call, or a vector of another width leaves this arm empty so BM25 and
lexical still run.
"""

import asyncio
import logging

from src.core.config import settings
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.store import fetch_by_similarity, to_passage

logger = logging.getLogger(__name__)

# DECISION 2026-09-26: one model for the database. Was 1536 on the OpenAI template.
EMBEDDING_DIM = settings.EMBEDDING_DIMENSIONS

_client: object | None = None


async def similarity_passages(session, query: SearchQuery, limit: int) -> list[Passage]:
    """Nearest in-force chunks. An unusable vector yields an empty list."""
    embedding = await _query_vector(query)
    if embedding is None or len(embedding) != EMBEDDING_DIM:
        return []
    hits = await fetch_by_similarity(session, query.incident_date, list(embedding), limit)
    return [to_passage(hit) for hit in hits]


async def _query_vector(query: SearchQuery) -> tuple[float, ...] | None:
    """Use a vector the caller already computed, otherwise embed ``query.text``."""
    if query.embedding is not None:
        return query.embedding
    text = query.text.strip()
    if not text:
        return None
    client = _embedding_client()
    if client is None:
        return None
    from src.services.embeddings_client import PURPOSE_QUERY, new_run_id

    try:
        vectors = await asyncio.to_thread(
            client.embed,
            [text],
            purpose=PURPOSE_QUERY,
            run_id=new_run_id("cite"),
        )
    except Exception:
        logger.exception("similarity query embed failed")
        return None
    if not vectors:
        return None
    return tuple(vectors[0])


def _embedding_client():
    """One audited client per process. An empty key leaves the arm idle."""
    global _client
    if _client is not None:
        return _client
    if not settings.MISTRAL_API_KEY:
        return None
    from src.services.embeddings_client import EmbeddingClient

    _client = EmbeddingClient()
    return _client
