"""Validate a planner decision and merge it into stored facts.

Python decides which facts count. The decision's requested action is only a hint.
"""

import re
from dataclasses import dataclass

from src.features.clarify.model.assess import ClarifyPlan, FactConflict, StoredFact, _all_confirmed, _missing
from src.features.clarify.model.catalog import ABSENCE, GENERAL, LATE, catalog_keys, detect_family, required_specs
from src.features.clarify.model.decision import ClarifyDecision, ExtractedFact, UserIntent
from src.features.clarify.model.extract import _flag, explicit_facts, extract_facts

_MIN_FACT_CONFIDENCE = 0.5
_MIN_FAMILY_CONFIDENCE = 0.6
_CONFIRMING = frozenset({UserIntent.CONFIRM_FACTS, UserIntent.CORRECT_FACTS})
_FLAG_KEYS = frozenset({"minutes_made", "explanation_requested"})
_COUNT_KEYS = frozenset({"absence_days", "late_days"})
_NONE = re.compile(r"(?<![a-z])none(?![a-z])")
_CONTRACTS = (
    ("không xác định thời hạn", "không xác định thời hạn"),
    ("khong xac dinh thoi han", "không xác định thời hạn"),
    ("indefinite", "không xác định thời hạn"),
    ("xác định thời hạn", "xác định thời hạn"),
    ("xac dinh thoi han", "xác định thời hạn"),
    ("fixed_term", "xác định thời hạn"),
    ("fixed term", "xác định thời hạn"),
    ("mùa vụ", "mùa vụ"),
    ("mua vu", "mùa vụ"),
    ("seasonal", "mùa vụ"),
    ("thử việc", "thử việc"),
    ("thu viec", "thử việc"),
    ("probation", "thử việc"),
)
_NOTICES = (
    ("không thông báo", "không báo"),
    ("khong thong bao", "không báo"),
    ("chẳng báo", "không báo"),
    ("chang bao", "không báo"),
    ("không báo", "không báo"),
    ("khong bao", "không báo"),
    ("không xin", "không báo"),
    ("khong xin", "không báo"),
    ("điện thoại", "điện thoại"),
    ("dien thoai", "điện thoại"),
    ("gọi điện", "điện thoại"),
    ("goi dien", "điện thoại"),
    ("tin nhắn", "tin nhắn"),
    ("tin nhan", "tin nhắn"),
    ("zalo", "tin nhắn"),
    ("thư điện tử", "email"),
    ("email", "email"),
    ("nộp đơn", "đơn"),
    ("gửi đơn", "đơn"),
    ("bằng đơn", "đơn"),
    ("trực tiếp", "trực tiếp"),
)


@dataclass(frozen=True)
class _Read:
    key: str
    value: str
    evidence: str


def apply_decision(
    text: str,
    stored: dict[str, StoredFact],
    decision: ClarifyDecision,
    *,
    fallback: bool = False,
) -> ClarifyPlan:
    """Merge a validated decision. Confirmed values stay until the user accepts a replacement."""
    ignored: list[str] = []
    ambiguous: list[str] = []
    reads = _reads(decision, ignored, ambiguous)
    reads.extend(_explicit_reads(text))
    if fallback:
        reads.extend(_rule_reads(text, {item.key for item in reads}))
    family = _family(stored, decision, [item.key for item in reads])
    allowed = {spec.key for spec in required_specs(family)}
    merged = dict(stored)
    conflicts: list[FactConflict] = []
    accepted: list[str] = []
    allow_confirm = decision.user_intent in _CONFIRMING
    confirmed_keys = {item.key for item in decision.confirmation_updates if item.confirmed and item.key in allowed}
    for item in reads:
        if item.key not in allowed:
            ignored.append(item.key)
            continue
        _place(merged, conflicts, stored, item, allow_confirm and item.key in confirmed_keys)
        accepted.append(item.key)
    if allow_confirm:
        _confirm_stored(merged, stored, conflicts, confirmed_keys)
    _accept_present(family, merged, conflicts)
    missing = _missing(family, merged)
    locked = not missing and _all_confirmed(family, merged) and not conflicts
    return ClarifyPlan(
        family=family,
        merged=merged,
        missing_keys=missing,
        locked=locked,
        conflicts=tuple(conflicts),
        requested_action=decision.requested_action.value,
        planner_fallback=fallback,
        user_intent=decision.user_intent.value,
        ambiguities=tuple(dict.fromkeys(ambiguous)),
        validation=_validation(ignored, ambiguous),
        accepted_keys=tuple(dict.fromkeys(accepted)),
    )


def _reads(decision: ClarifyDecision, ignored: list[str], ambiguous: list[str]) -> list[_Read]:
    corrected = {item.key for item in decision.corrections}
    reads = []
    for item in (*decision.corrections, *decision.extracted_facts):
        if item.key in corrected and item not in decision.corrections:
            continue
        read = _read(item, ignored, ambiguous)
        if read is not None:
            reads.append(read)
    return reads


def _read(item: ExtractedFact, ignored: list[str], ambiguous: list[str]) -> _Read | None:
    if item.key not in catalog_keys():
        if item.key:
            ignored.append(item.key)
        return None
    if item.ambiguous or item.confidence < _MIN_FACT_CONFIDENCE:
        ambiguous.append(item.key)
        return None
    value = canonicalize(item.key, item.value, item.evidence)
    if value is None:
        ambiguous.append(item.key)
        return None
    return _Read(item.key, value, item.evidence.strip())


def _rule_reads(text: str, taken: set[str]) -> list[_Read]:
    """Use the old reader only after the planner failed. Values stay unconfirmed."""
    reads = []
    for key, raw in extract_facts(detect_family(text), text).items():
        if key in taken:
            continue
        value = canonicalize(key, raw, raw, explicit=True)
        if value is not None:
            reads.append(_Read(key, value, raw))
    return reads


def _explicit_reads(text: str) -> list[_Read]:
    reads = []
    for key, raw in explicit_facts(text, catalog_keys()).items():
        value = canonicalize(key, raw, raw, explicit=True)
        if value is not None:
            reads.append(_Read(key, value, raw))
    return reads


def _place(
    merged: dict[str, StoredFact],
    conflicts: list[FactConflict],
    _stored: dict[str, StoredFact],
    item: _Read,
    _accept_replacement: bool,
) -> None:
    merged[item.key] = StoredFact(item.value, True)
    conflicts[:] = [conflict for conflict in conflicts if conflict.key != item.key]


def _accept_present(family: str, merged: dict[str, StoredFact], conflicts: list[FactConflict]) -> None:
    """A filled fact is the working value. The chat does not wait for a separate confirmation."""
    blocked = {conflict.key for conflict in conflicts}
    for spec in required_specs(family):
        if spec.key in blocked:
            continue
        item = merged.get(spec.key)
        if item is None or not item.value.strip() or item.confirmed:
            continue
        merged[spec.key] = StoredFact(item.value, True)


def _confirm_stored(
    merged: dict[str, StoredFact],
    stored: dict[str, StoredFact],
    conflicts: list[FactConflict],
    keys: set[str],
) -> None:
    blocked = {conflict.key for conflict in conflicts}
    for key in keys:
        if key in blocked:
            continue
        current = merged.get(key)
        previous = stored.get(key)
        if current is None or previous is None or not current.value.strip():
            continue
        if previous.value != current.value:
            continue
        merged[key] = StoredFact(current.value, True)


def _family(stored: dict[str, StoredFact], decision: ClarifyDecision, keys: list[str]) -> str:
    if any(item.confirmed for item in stored.values()):
        implied = _implied(stored)
        if implied:
            return implied
    if decision.family_confidence >= _MIN_FAMILY_CONFIDENCE:
        return decision.family.value
    return _implied_keys(keys) or _implied(stored) or GENERAL


def _implied(stored: dict[str, StoredFact]) -> str | None:
    return _implied_keys([key for key, item in stored.items() if item.value.strip()])


def _implied_keys(keys: list[str] | set[str]) -> str | None:
    found = set(keys)
    if "absence_days" in found or "notice_form" in found:
        return ABSENCE
    if "late_days" in found:
        return LATE
    if "violation_summary" in found:
        return GENERAL
    return None


def canonicalize(key: str, value: str, evidence: str, *, explicit: bool = False) -> str | None:
    """Map a planner value onto the phrases the rest of the case path already stores."""
    raw = value.strip()
    proof = raw if explicit else evidence.strip()
    if not raw or not proof:
        return None
    if key in _FLAG_KEYS:
        canonical = _flag(raw)
        if canonical is None or _flag(proof) != canonical:
            return None
        return canonical
    if key == "contract_type":
        canonical = _match_contract(raw)
        if canonical is None or _match_contract(proof) != canonical:
            return None
        return canonical
    if key == "notice_form":
        canonical = _match_notice(raw)
        if canonical is None or _match_notice(proof) != canonical:
            return None
        return canonical
    if key in _COUNT_KEYS:
        return _count(key, raw, proof)
    if key == "violation_summary":
        if len(raw) < 3 or len(proof) < 3:
            return None
        if raw.casefold() not in proof.casefold() and proof.casefold() not in raw.casefold():
            return None
        return raw[:180]
    return None


def _count(key: str, value: str, proof: str) -> str | None:
    match = re.search(r"\d+", value)
    if match is None or match.group(0) not in proof:
        return None
    number = match.group(0)
    folded = value.casefold()
    unit = "lần" if key == "late_days" and ("lần" in folded or "lan" in folded) else "ngày"
    phrase = f"{number} {unit}"
    window = _window(folded)
    if window is None or unit != "ngày":
        return phrase
    if _window(proof.casefold()) != window:
        return None
    return f"{phrase} trong {window}"


def _window(folded: str) -> str | None:
    if re.search(r"30\s*ngày|một tháng|1 tháng", folded):
        return "30 ngày"
    if re.search(r"365\s*ngày|một năm|12\s*tháng", folded):
        return "365 ngày"
    return None


def _match_contract(text: str) -> str | None:
    folded = text.casefold()
    for needle, label in _CONTRACTS:
        if needle in folded:
            return label
    return None


def _match_notice(text: str) -> str | None:
    folded = text.casefold()
    for needle, label in _NOTICES:
        if needle in folded:
            return label
    if _NONE.search(folded):
        return "không báo"
    return None


def _validation(ignored: list[str], ambiguous: list[str]) -> str:
    parts = []
    if ignored:
        parts.append("ignored=" + ",".join(dict.fromkeys(ignored)))
    if ambiguous:
        parts.append("ambiguous=" + ",".join(dict.fromkeys(ambiguous)))
    return ";".join(parts) if parts else "ok"
