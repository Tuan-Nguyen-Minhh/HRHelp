"""Choose whole passages by evidence need; expose gaps instead of hiding omissions."""

from dataclasses import dataclass, replace
from functools import lru_cache

from src.core.config import settings
from src.features.answer.model.layers import BasisLayer, layer_of
from src.features.cite.model.passage import Passage
from src.features.cite.model.rerank import document_text


@dataclass(frozen=True)
class EvidenceSelection:
    passages: list[Passage]
    gaps: tuple[str, ...]
    size: int
    size_unit: str


@lru_cache(maxsize=4)
def _tokenizer(path: str):
    from tokenizers import Tokenizer
    return Tokenizer.from_file(path)


def evidence_size(passage: Passage) -> int:
    content = document_text(passage)
    if settings.SYNTHESIS_TOKENIZER_PATH:
        return len(_tokenizer(settings.SYNTHESIS_TOKENIZER_PATH).encode(content).ids)
    return len(content.encode("utf-8"))


def source_role(passage: Passage) -> str:
    layer = layer_of(passage.policy_type, passage.policy_code, passage.policy_name)
    return {BasisLayer.LEGAL_BASIS: "authority", BasisLayer.INTERNAL_RULE: "internal_rule",
            BasisLayer.PRECEDENT: "precedent", BasisLayer.INSPECTION_RISK: "administrative_penalty"}[layer]


def select_evidence(passages: list[Passage], *, status: str = "OK") -> EvidenceSelection:
    budget = (settings.RETRIEVAL_EVIDENCE_TOKEN_BUDGET if settings.SYNTHESIS_TOKENIZER_PATH
              else settings.RETRIEVAL_EVIDENCE_MAX_BYTES)
    unit = "tokens" if settings.SYNTHESIS_TOKENIZER_PATH else "utf8_bytes"
    ordered = []
    for role in ("internal_rule", "authority", "conditions", "procedure"):
        candidates = [item for item in passages if source_role(item) in {"internal_rule", "authority"}
                      and (role in {"conditions", "procedure"} or source_role(item) == role)]
        candidates.sort(key=lambda item: dict(item.facet_scores).get(role, item.rerank_score or 0), reverse=True)
        ordered.extend(candidates[:2])
    ordered.extend(passages)
    kept, seen, texts, omitted = [], set(), set(), []
    used = 0
    for item in ordered:
        if item.chunk_id in seen:
            continue
        seen.add(item.chunk_id)
        text_key = (item.policy_version_id, item.content.strip())
        if text_key in texts or source_role(item) not in {"internal_rule", "authority"}:
            continue
        best = max([item.rerank_score or 0, *[score for _, score in item.facet_scores]])
        if settings.RERANK_MIN_SCORE is not None and best < settings.RERANK_MIN_SCORE:
            continue
        size = evidence_size(item)
        if used + size > budget or len(kept) >= settings.RETRIEVAL_FINAL_K:
            omitted.append(item)
            continue
        used += size
        texts.add(text_key)
        kept.append(item)
    gaps = []
    for role in ("internal_rule", "authority"):
        if not any(source_role(item) == role for item in kept):
            gaps.append(f"MISSING_{role.upper()}")
    # Do not silently discard cited dependencies or exceptions when limiting context.
    if any(item.origin == "graph" or any(word in item.content.casefold() for word in
           ("trừ trường hợp", "không được xử lý", "ngoại lệ")) for item in omitted):
        gaps.append("EVIDENCE_BUDGET_EXCEEDED")
    if status != "OK":
        gaps.append(f"RERANK_{status}")
    quality = "OK" if not gaps else "INCOMPLETE" if status == "OK" else "DEGRADED"
    return EvidenceSelection([replace(item, retrieval_status=quality, evidence_gaps=tuple(gaps)) for item in kept],
                             tuple(gaps), used, unit)
