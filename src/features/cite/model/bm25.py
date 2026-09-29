"""Okapi BM25 over in-force chunk text.

This is one retriever in the cite pipeline. It does not see embeddings.
"""

import math
import re
from dataclasses import replace

from src.features.cite.model.passage import Passage

_TOKEN = re.compile(r"\w+", re.UNICODE)
_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens. Vietnamese letters stay intact."""
    return [token.casefold() for token in _TOKEN.findall(text)]


def bm25_rank(passages: list[Passage], terms: list[str], limit: int) -> list[Passage]:
    """Score passages against ``terms`` and keep the strongest ``limit``."""
    if not passages or not terms or limit <= 0:
        return []
    documents = [tokenize(passage.content) for passage in passages]
    query = [token for term in terms for token in tokenize(term)]
    if not query:
        return []
    scores = _scores(documents, query)
    ranked = sorted(zip(passages, scores, strict=True), key=lambda item: item[1], reverse=True)
    kept = [replace(passage, score=score) for passage, score in ranked if score > 0]
    return kept[:limit]


def _scores(documents: list[list[str]], query: list[str]) -> list[float]:
    count = len(documents)
    average = sum(len(document) for document in documents) / count
    document_frequency: dict[str, int] = {}
    for document in documents:
        for token in set(document):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    scored = []
    for document in documents:
        frequency: dict[str, int] = {}
        for token in document:
            frequency[token] = frequency.get(token, 0) + 1
        length = len(document) or 1
        total = 0.0
        for token in query:
            seen = document_frequency.get(token, 0)
            if seen == 0 or token not in frequency:
                continue
            inverse = _inverse(count, seen)
            found = frequency[token]
            numerator = found * (_K1 + 1)
            denominator = found + _K1 * (1 - _B + _B * length / average)
            total += inverse * numerator / denominator
        scored.append(total)
    return scored


def _inverse(documents: int, seen: int) -> float:
    return math.log(1 + (documents - seen + 0.5) / (seen + 0.5))
