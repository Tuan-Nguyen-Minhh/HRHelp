"""Article-outline fallback when similarity, BM25, and lexical return nothing.

Phrases are wider than the twelve-term query list. A hit may sit in the
article title, the section title, or the chunk text. The selector keeps the
earliest chunk of each article and does not fill a miss with arbitrary chunks.
"""

from dataclasses import replace

from src.features.cite.model.passage import Passage
from src.features.cite.model.store import ChunkHit, to_passage
from src.features.clarify.model.catalog import ABSENCE, GENERAL, LATE

_ANCHORS = {
    ABSENCE: (
        "sa thải",
        "kỷ luật",
        "nghỉ không phép",
        "tự ý bỏ việc",
        "đơn phương chấm dứt",
    ),
    LATE: (
        "kỷ luật",
        "đi muộn",
        "nội quy",
        "thời giờ làm việc",
    ),
    GENERAL: (
        "kỷ luật lao động",
        "nội quy",
        "hình thức kỷ luật",
    ),
}
_TYPE_RANK = {"LAW": 0, "DECREE": 1, "INTERNAL_RULE": 2, "PRECEDENT": 3}


def anchors_for(family: str) -> tuple[str, ...]:
    """Outline phrases for one case family. Unknown families use the general list."""
    return _ANCHORS.get(family, _ANCHORS[GENERAL])


def retrieval_mode(passages: list[Passage]) -> str:
    """``empty`` abstains. ``page_index`` means every kept chunk came from the outline."""
    if not passages:
        return "empty"
    if all(passage.origin == "page_index" for passage in passages):
        return "page_index"
    return "hybrid"


def select_article_heads(hits: list[ChunkHit], phrases: tuple[str, ...] | list[str], limit: int) -> list[Passage]:
    """One lead chunk per article, ordered law, decree, then internal rule."""
    folded = tuple(phrase.casefold() for phrase in phrases if phrase.strip())
    if limit <= 0 or not folded:
        return []
    best: dict[tuple[object, str], ChunkHit] = {}
    for hit in hits:
        if not _matches(hit, folded):
            continue
        key = (hit.policy_version_id, hit.article or "")
        current = best.get(key)
        if current is None or hit.chunk_index < current.chunk_index:
            best[key] = hit
    ordered = sorted(best.values(), key=_order)
    return [_as_page(hit) for hit in ordered[:limit]]


def _matches(hit: ChunkHit, phrases: tuple[str, ...]) -> bool:
    haystack = " ".join(part for part in (hit.article_title, hit.section_title, hit.content) if part).casefold()
    return any(phrase in haystack for phrase in phrases)


def _order(hit: ChunkHit) -> tuple:
    return (_TYPE_RANK.get(hit.policy_type or "", 9), hit.policy_code, _article_sort(hit.article), hit.chunk_index)


def _article_sort(article: str | None) -> tuple:
    if not article:
        return (1, 0, "")
    digits: list[str] = []
    for char in article:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return (0, int("".join(digits)) if digits else 0, article)


def _as_page(hit: ChunkHit) -> Passage:
    return replace(to_passage(hit), score=0.0, origin="page_index")
