"""Pick one company level from the passages feature 5 actually retrieved.

The internal-rule passage has to match the case narrative. The law and guiding
decree passages name the forms the company may use. Dismissal stays in that set
only when a retrieved sentence carries it and the case meets the condition
written in that sentence. Day counts are read from the text. An administrative
penalty and a precedent never enter this comparison.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from src.features.answer.schema import SANCTION_LABELS

_RANK = {
    "WARNING": 1,
    "REPRIMAND": 2,
    "WAGE_POSTPONEMENT": 3,
    "DEMOTION": 4,
    "DISMISSAL": 5,
}
_PHRASES = (
    ("WAGE_POSTPONEMENT", ("kéo dài thời hạn nâng lương", "kéo dài nâng lương", "hoãn nâng lương")),
    ("DISMISSAL", ("sa thải",)),
    ("DEMOTION", ("cách chức",)),
    ("REPRIMAND", ("cảnh cáo",)),
    ("WARNING", ("khiển trách",)),
)
_PAIR = re.compile(
    r"(\d+)\s*ngày\b(?:(?!\d).){0,60}?trong(?:\s+thời\s+hạn|\s+vòng)?\s+(\d+)\s*ngày",
    re.IGNORECASE,
)
_UNDER = re.compile(r"dưới\s+(\d+)\s*ngày", re.IGNORECASE)
_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOP = frozenset(
    {
        "của", "và", "cho", "với", "một", "các", "được", "trong", "ngày", "nhân", "viên",
        "đã", "chưa", "này", "khi", "theo", "hoặc", "nhưng", "về", "là", "có", "để",
        "nên", "vẫn", "người", "lao", "động", "công", "ty", "hình", "thức", "xử", "lý",
        "kỷ", "luật", "áp", "dụng", "trường", "hợp", "mức", "quy", "định", "nội", "thì",
        "bị", "đến", "từ", "sau", "đây", "tại", "nơi", "làm", "cũng", "như", "nếu", "mà",
        "những", "đó", "ra", "vào", "trên", "quá", "tháng", "năm", "thời", "hạn", "cộng",
        "dồn", "tính", "tiên", "chính", "đáng", "lý", "do", "bao", "gồm", "liên", "tục",
        "trở", "lên",
    }
)
_NO_CEILING = "Chưa đọc được mức nào từ luật và nghị định đã retrieval. Chưa chốt mức."
_NO_MATCH = "Đã có nội quy nhưng không đoạn nào khớp hành vi của hồ sơ. Chưa chốt mức."
_ABOVE = "Nội quy khớp hành vi nêu mức cao hơn trần của luật và nghị định đã retrieval. Chưa chốt mức vượt trần."
_MANY = "Nội quy khớp hành vi còn nhiều mức nằm trong trần. Chưa chọn mức nặng hơn."


class _Chunk(Protocol):
    content: str


@dataclass(frozen=True)
class Reconciliation:
    """The level the retrieved texts support, or an open result."""

    sanction_type: str | None
    risk_level: str
    rationale: str


def reconcile(legal_passages: list[_Chunk], rule_passages: list[_Chunk], case_text: str) -> Reconciliation:
    """Return the one level that is both in the matching rule and inside the retrieved ceiling."""
    permitted = _permitted(legal_passages, case_text)
    matched = _company_levels(rule_passages, case_text)
    if not permitted:
        return Reconciliation(None, "HIGH", _NO_CEILING)
    if not matched:
        return Reconciliation(None, "HIGH", _NO_MATCH)
    allowed = matched & permitted
    if not allowed:
        return Reconciliation(None, "HIGH", _ABOVE)
    if len(allowed) > 1:
        return Reconciliation(None, "MEDIUM", _MANY)
    return Reconciliation(next(iter(allowed)), "MEDIUM", _locked_reason(next(iter(allowed))))


def _locked_reason(level: str) -> str:
    label = SANCTION_LABELS[level]
    reason = (
        f"Đoạn nội quy khớp hành vi nêu {label}. "
        "Mức này còn trong trần đọc từ luật và nghị định đã retrieval. "
        f"Đề xuất {label} để pháp chế xem."
    )
    if level == "DISMISSAL":
        return reason + " Không đề xuất chấm dứt hợp đồng (TERMINATION)."
    return reason


def _permitted(passages: list[_Chunk], case_text: str) -> set[str]:
    """Act-specific sentences cap the catalog. A catalog alone does not authorize dismissal."""
    named = _named(passages)
    if "DISMISSAL" in named and not _dismissal_supported(passages, case_text):
        named.discard("DISMISSAL")
    matched = _matched_levels(passages, case_text)
    if not matched:
        return named
    ceiling = max(matched, key=_RANK.__getitem__)
    return {level for level in named if _RANK[level] <= _RANK[ceiling]}


def _matched_levels(passages: list[_Chunk], case_text: str) -> set[str]:
    found: set[str] = set()
    for passage in passages:
        for _score, levels in _offers(passage.content, case_text):
            found.update(levels)
    return found


def _named(passages: list[_Chunk]) -> set[str]:
    found: set[str] = set()
    for passage in passages:
        found.update(_levels_in(passage.content))
    return found


def _dismissal_supported(passages: list[_Chunk], case_text: str) -> bool:
    for passage in passages:
        for _score, levels in _offers(passage.content, case_text):
            if "DISMISSAL" in levels:
                return True
    return False


def _company_levels(passages: list[_Chunk], case_text: str) -> set[str]:
    offers = [offer for passage in passages for offer in _offers(passage.content, case_text)]
    if not offers:
        return set()
    best = max(score for score, _levels in offers)
    found: set[str] = set()
    for score, levels in offers:
        if score == best:
            found.update(levels)
    return found


def _offers(text: str, case_text: str) -> list[tuple[int, frozenset[str]]]:
    """A chapeau that names the form covers later clauses that only state the ground."""
    header: frozenset[str] = frozenset()
    offers: list[tuple[int, frozenset[str]]] = []
    for sentence in _sentences(text):
        own = _levels_in(sentence)
        if own:
            header = frozenset(own)
        if not header:
            continue
        score = _score(sentence, case_text)
        if score:
            offers.append((score, header))
    return offers


def _score(sentence: str, case_text: str) -> int:
    overlap = _overlap(sentence, case_text)
    gate = _gate(sentence, case_text)
    if gate is False or overlap == 0:
        return 0
    if gate is True:
        return 100 + overlap
    return overlap


def _gate(sentence: str, case_text: str) -> bool | None:
    """True or False when the sentence states a day condition. None when it states none."""
    pairs = _pairs(sentence)
    if pairs:
        facts = _pairs(case_text)
        return any(any(window == fact_window and days >= need for days, fact_window in facts) for need, window in pairs)
    under = _UNDER.search(sentence.casefold())
    if under is None:
        return None
    counted = _day_count(case_text)
    return counted is not None and counted < int(under.group(1))


def _pairs(text: str) -> list[tuple[int, int]]:
    return [(int(need), int(window)) for need, window in _PAIR.findall(text.casefold())]


def _day_count(text: str) -> int | None:
    pairs = _pairs(text)
    if pairs:
        return pairs[0][0]
    found = re.search(r"(\d+)\s*ngày", text.casefold())
    if found is None:
        return None
    return int(found.group(1))


def _overlap(sentence: str, case_text: str) -> int:
    left = _tokens(sentence)
    right = _tokens(case_text)
    left_compounds = {token for token in left if token.startswith("không_")}
    right_compounds = {token for token in right if token.startswith("không_")}
    compounds = left_compounds & right_compounds
    bigrams = set(zip(left, left[1:], strict=False)) & set(zip(right, right[1:], strict=False))
    return len(compounds) + len(bigrams)


def _tokens(text: str) -> list[str]:
    raw = _TOKEN.findall(_strip_levels(text))
    merged: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == "không" and index + 1 < len(raw):
            merged.append(f"không_{raw[index + 1]}")
            index += 2
            continue
        merged.append(token)
        index += 1
    kept: list[str] = []
    for token in merged:
        if token.startswith("không_"):
            kept.append(token)
        elif token.isdigit() or len(token) < 2 or token in _STOP:
            continue
        else:
            kept.append(token)
    return kept


def _strip_levels(text: str) -> str:
    folded = text.casefold()
    for _level, phrases in _PHRASES:
        for phrase in phrases:
            folded = folded.replace(phrase, " ")
    return folded


def _levels_in(text: str) -> set[str]:
    folded = text.casefold()
    return {level for level, phrases in _PHRASES if any(phrase in folded for phrase in phrases)}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[\n.;]+", text) if part.strip()]
