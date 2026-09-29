"""Last stage of the cite pipeline.

The default keeps the fused order. Replace ``rerank`` with a cross-encoder
when that model is ready. The graph node stays the same.
"""

from src.features.cite.model.passage import Passage


def rerank(query: str, passages: list[Passage]) -> list[Passage]:
    """Return passages in the order the sanction agent should read."""
    del query
    return list(passages)
