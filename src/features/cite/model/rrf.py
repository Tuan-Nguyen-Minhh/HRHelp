"""Reciprocal rank fusion for the cite retrievers."""

from dataclasses import replace
from uuid import UUID

from src.features.cite.model.passage import Passage

_RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[Passage]], limit: int, k: int = _RRF_K) -> list[Passage]:
    """Fuse ranked lists. A chunk in more lists, and higher in each, sorts first."""
    scores: dict[UUID, float] = {}
    chosen: dict[UUID, Passage] = {}
    for ranking in rankings:
        for rank, passage in enumerate(ranking, start=1):
            scores[passage.chunk_id] = scores.get(passage.chunk_id, 0.0) + 1 / (k + rank)
            chosen.setdefault(passage.chunk_id, passage)
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [replace(chosen[chunk_id], score=scores[chunk_id]) for chunk_id in ordered[:limit]]
