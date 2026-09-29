"""Retrieval sub-graph: similarity, BM25, and lexical search, then RRF, then rerank.

Each retriever writes its own channel. RRF waits until all three have finished.
A failing retriever yields an empty list and the other arms still fuse.
An empty rerank walks the article outline. A second miss leaves the hits empty.
"""

import logging
from collections.abc import Awaitable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.features.cite.model.bm25 import bm25_rank
from src.features.cite.model.page_index import anchors_for, select_article_heads
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.rank import rank_passages
from src.features.cite.model.rerank import rerank
from src.features.cite.model.rrf import reciprocal_rank_fusion
from src.features.cite.model.similarity import similarity_passages
from src.features.cite.model.store import fetch_article_index, fetch_candidates, fetch_in_force, to_passage

logger = logging.getLogger(__name__)

RETRIEVAL_K = 8
_BM25_POOL = 200
_INDEX_POOL = 80


class RetrievalState(TypedDict, total=False):
    """Channels of one cite. ``hits`` is the list the handoff message carries."""

    query: SearchQuery
    terms: list[str]
    similarity: list[Passage]
    bm25: list[Passage]
    lexical: list[Passage]
    fused: list[Passage]
    hits: list[Passage]
    retrieval: str


def build_retrieval_graph(session) -> CompiledStateGraph:
    """Compile the production retrievers against ``session``."""

    async def similarity(state: RetrievalState) -> dict:
        return await _arm("similarity", similarity_passages(session, state["query"], RETRIEVAL_K))

    async def bm25(state: RetrievalState) -> dict:
        return await _arm("bm25", _bm25(session, state))

    async def lexical(state: RetrievalState) -> dict:
        return await _arm("lexical", _lexical(session, state))

    async def page_index(state: RetrievalState) -> dict:
        return await _page_index(session, state)

    return compile_retrieval(similarity, bm25, lexical, page_index)


def compile_retrieval(similarity, bm25, lexical, page_index=None) -> CompiledStateGraph:
    """Compile three retriever nodes into RRF and rerank. Tests pass fakes here."""
    graph = StateGraph(RetrievalState)
    graph.add_node("similarity", similarity)
    graph.add_node("bm25", bm25)
    graph.add_node("lexical", lexical)
    graph.add_node("rrf", rrf_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("page_index", page_index or _abstain)
    graph.add_edge(START, "similarity")
    graph.add_edge(START, "bm25")
    graph.add_edge(START, "lexical")
    graph.add_edge(["similarity", "bm25", "lexical"], "rrf")
    graph.add_edge("rrf", "rerank")
    graph.add_conditional_edges("rerank", _after_rerank, {"done": END, "page_index": "page_index"})
    graph.add_edge("page_index", END)
    return graph.compile()


def rrf_node(state: RetrievalState) -> dict:
    """Fuse the three ranked lists. Empty arms do not add rank mass."""
    rankings = [list(state.get("similarity") or []), list(state.get("bm25") or []), list(state.get("lexical") or [])]
    return {"fused": reciprocal_rank_fusion(rankings, RETRIEVAL_K)}


def rerank_node(state: RetrievalState) -> dict:
    """Apply the rerank hook. The default hook keeps fused order."""
    query = state["query"]
    hits = rerank(query.text, list(state.get("fused") or []))
    if not hits:
        return {"hits": []}
    return {"hits": hits, "retrieval": "hybrid"}


def _after_rerank(state: RetrievalState) -> str:
    """Walk the article outline only after every ranked arm missed."""
    if state.get("hits"):
        return "done"
    return "page_index"


async def _abstain(_state: RetrievalState) -> dict:
    return {"hits": [], "retrieval": "empty"}


async def _page_index(session, state: RetrievalState) -> dict:
    query = state["query"]
    phrases = list(anchors_for(query.family))
    try:
        rows = await fetch_article_index(session, query.incident_date, phrases, _INDEX_POOL)
    except Exception:
        logger.exception("page_index retriever failed")
        return {"hits": [], "retrieval": "empty"}
    hits = select_article_heads(rows, phrases, RETRIEVAL_K)
    if not hits:
        return {"hits": [], "retrieval": "empty"}
    return {"hits": hits, "retrieval": "page_index"}


async def _bm25(session, state: RetrievalState) -> list[Passage]:
    hits = await fetch_in_force(session, state["query"].incident_date, _BM25_POOL)
    passages = [to_passage(hit) for hit in hits]
    return bm25_rank(passages, list(state.get("terms") or []), RETRIEVAL_K)


async def _lexical(session, state: RetrievalState) -> list[Passage]:
    hits = await fetch_candidates(session, state["query"].incident_date, list(state.get("terms") or []))
    passages = [to_passage(hit) for hit in hits]
    return rank_passages(passages, list(state.get("terms") or []), RETRIEVAL_K)


async def _arm(name: str, awaitable: Awaitable[list[Passage]]) -> dict:
    try:
        return {name: await awaitable}
    except Exception:
        logger.exception("%s retriever failed", name)
        return {name: []}
