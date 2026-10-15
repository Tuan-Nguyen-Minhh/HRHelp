"""One-hop citation expansion after RRF, before the unchanged rerank hook."""

import logging
from dataclasses import replace

from src.core.config import settings
from src.features.cite.model.passage import Passage
from src.features.cite.model.store import fetch_graph_neighbors

logger = logging.getLogger(__name__)

GRAPH_SEED_K = 5
GRAPH_MAX_EXPANSION = 12
GRAPH_EDGE_DECAY = 0.6
GRAPH_MIN_CONFIDENCE = "HIGH"


def expand_passages(fused: list[Passage], neighbors: list[Passage]) -> list[Passage]:
    """Keep original hits intact and add at most twelve distinct, decayed neighbors."""
    if not fused:
        return []
    score = max(passage.score for passage in fused[:GRAPH_SEED_K]) * GRAPH_EDGE_DECAY
    seen = {passage.chunk_id for passage in fused}
    added = []
    for passage in neighbors:
        if passage.chunk_id in seen:
            continue
        seen.add(passage.chunk_id)
        added.append(replace(passage, score=score, origin="graph"))
        if len(added) == GRAPH_MAX_EXPANSION:
            break
    # Python's stable sort keeps fused ahead of neighbors when scores tie.
    return sorted([*fused, *added], key=lambda passage: passage.score, reverse=True)


def expand_node(session):
    """Bind graph reads to the request session; failures preserve the RRF result."""

    async def expand(state: dict) -> dict:
        fused = list(state.get("fused") or [])
        if not fused:
            return {"expanded": fused}
        seeds = list(state.get("seeds", fused[:GRAPH_SEED_K]))
        if not seeds:
            return {"expanded": fused}
        try:
            # A database error must not poison the caller's transaction/audit writes.
            async with session.begin_nested():
                neighbors = await fetch_graph_neighbors(
                    session,
                    state["query"].incident_date,
                    [passage.chunk_id for passage in seeds[:GRAPH_SEED_K]],
                    GRAPH_MAX_EXPANSION,
                    min_confidence=GRAPH_MIN_CONFIDENCE,
                    exclude_chunk_ids=[passage.chunk_id for passage in fused],
                    include_incoming=settings.RETRIEVAL_GRAPH_INCOMING,
                )
            return {"expanded": expand_passages(fused, neighbors)}
        except Exception:
            logger.exception("graph expansion failed; preserving fused passages")
            return {"expanded": fused, "graph_status": "FAILED"}

    return expand
