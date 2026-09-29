"""Rank passages by how many search terms they contain."""

from dataclasses import replace

from src.features.cite.model.passage import Passage


def rank_passages(passages: list[Passage], terms: list[str], limit: int) -> list[Passage]:
    """Keep the strongest distinct chunks. A passage that shares no term is dropped."""
    scored = [replace(passage, score=_overlap(passage.content, terms)) for passage in passages]
    scored = [passage for passage in scored if passage.score > 0]
    scored.sort(key=lambda passage: passage.score, reverse=True)
    return _dedupe(scored)[:limit]


def _overlap(content: str, terms: list[str]) -> float:
    if not terms:
        return 0.0
    folded = content.casefold()
    hits = sum(1 for term in terms if term.casefold() in folded)
    return hits / len(terms)


def _dedupe(passages: list[Passage]) -> list[Passage]:
    seen: set[object] = set()
    kept = []
    for passage in passages:
        if passage.chunk_id in seen:
            continue
        seen.add(passage.chunk_id)
        kept.append(passage)
    return kept
