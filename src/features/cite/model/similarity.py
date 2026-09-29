"""Vector retriever. It runs only when the query carries an embedding.

``document_chunks.embedding`` is 1024-dimensional (mistral-embed, DECISION
2026-09-26). A vector of another width is skipped so this arm cannot fail the
BM25 and lexical arms.
"""

from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.store import fetch_by_similarity, to_passage

# DECISION 2026-09-26: unified on mistral-embed 1024-dim.
# Was 1536 (OpenAI template) — fixed to match migration 0002_unify_mistral_embed.
EMBEDDING_DIM = 1024


async def similarity_passages(session, query: SearchQuery, limit: int) -> list[Passage]:
    """Nearest in-force chunks, or an empty list when no usable vector was supplied."""
    if query.embedding is None or len(query.embedding) != EMBEDDING_DIM:
        return []
    hits = await fetch_by_similarity(session, query.incident_date, list(query.embedding), limit)
    return [to_passage(hit) for hit in hits]
