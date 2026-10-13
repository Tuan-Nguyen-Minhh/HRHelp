"""Validate a planner decision and merge it into stored facts.

Python decides which facts count. The decision's requested action is only a hint.
"""

import re
from dataclasses import dataclass

from src.features.clarify.model.assess import ClarifyPlan, FactConflict, StoredFact, _all_confirmed, _missing
from src.features.clarify.model.catalog import (
    ABSENCE,
    GENERAL,
    LATE,
    FactSpec,
    catalog_keys,
    default_dynamic_specs,
    detect_family,
    fact_label,
    normalize_dynamic_key,
    safe_dynamic_key,
)
from src.features.clarify.model.decision import ClarifyDecision, ExtractedFact, RequestedAction, UserIntent
from src.features.clarify.model.extract import _flag, explicit_facts, extract_facts

_MIN_FACT_CONFIDENCE = 0.5
_MIN_FAMILY_CONFIDENCE = 0.6
_CONFIRMING = frozenset({UserIntent.CONFIRM_FACTS, UserIntent.CORRECT_FACTS})
_FLAG_KEYS = frozenset({"minutes_made", "explanation_requested"})
_COUNT_KEYS = frozenset({"absence_days", "late_days"})
_CRITICAL_AMENDMENT_KEYS = frozenset(
    {
        "incident_date",
        "incident_time",
        "violation_date",
        "violation_time",
        "discovery_date",
        "discovery_time",
        "employee_role",
        "evidence_available",
        "evidence_docs",
        "witnesses",
    }
)
_BLOCKED_DYNAMIC_WORDS = re.compile(
    r"(guilty|liable|liability|dismiss|dismissal|terminate|termination|sanction|penalty|valid|illegal|legal|fault|culpable|ket_luan|co_loi|sa_thai|cham_dut|ky_luat)"
)
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
    confirmed: bool = True


def apply_decision(
    text: str,
    stored: dict[str, StoredFact],
    decision: ClarifyDecision,
    *,
    fallback: bool = False,
    locked_keys: set[str] | None = None,
) -> ClarifyPlan:
    """Merge a validated decision. Confirmed values stay until the user accepts a replacement."""
    ignored: list[str] = []
    ambiguous: list[str] = []
    locked_keys = {normalize_dynamic_key(key) for key in (locked_keys or set()) if safe_dynamic_key(key)}
    initial_keys = {normalize_dynamic_key(item.key) for item in decision.fact_requirements}
    initial_keys.update(key for key in stored if safe_dynamic_key(key))
    initial_keys.update(locked_keys)
    initial_keys.update(catalog_keys())
    reads = _reads(decision, ignored, ambiguous, initial_keys, locked_keys)
    reads.extend(_explicit_reads(text))
    if fallback:
        reads.extend(_rule_reads(text, {item.key for item in reads}))
    family = _family(stored, decision, [item.key for item in reads])
    specs = _schema_specs(family, decision, stored, reads, ignored, locked_keys)
    allowed = {spec.key for spec in specs}
    merged = dict(stored)
    conflicts: list[FactConflict] = []
    accepted: list[str] = []
    allow_confirm = decision.user_intent in _CONFIRMING
    confirmed_keys = {
        normalize_dynamic_key(item.key)
        for item in decision.confirmation_updates
        if item.confirmed and normalize_dynamic_key(item.key) in allowed
    }
    for item in reads:
        if item.key not in allowed:
            ignored.append(item.key)
            continue
        _place(merged, conflicts, stored, item, allow_confirm and item.key in confirmed_keys)
        accepted.append(item.key)
    if allow_confirm:
        _confirm_stored(merged, stored, conflicts, confirmed_keys)
    _accept_present(family, merged, conflicts, specs)
    missing = _missing(family, merged, specs)
    locked = not missing and _all_confirmed(family, merged, specs) and not conflicts
    requested_action = _guard_requested_action(text, decision.requested_action)
    return ClarifyPlan(
        family=family,
        merged=merged,
        missing_keys=missing,
        locked=locked,
        conflicts=tuple(conflicts),
        requested_action=requested_action.value,
        planner_fallback=fallback,
        user_intent=decision.user_intent.value,
        ambiguities=tuple(dict.fromkeys(ambiguous)),
        validation=_validation(ignored, ambiguous),
        accepted_keys=tuple(dict.fromkeys(accepted)),
        specs=specs,
    )


def _guard_requested_action(text: str, action: RequestedAction) -> RequestedAction:
    """Keep workflow artifact requests out of the policy-QA branch."""
    folded = _fold(text)
    if _asks_for_minutes(folded):
        return RequestedAction.DRAFT_MINUTES
    if _asks_for_ticket(folded):
        return RequestedAction.CREATE_TICKET_PREVIEW
    if _asks_to_send_legal(folded):
        return RequestedAction.SEND_TO_LEGAL
    return action


def _asks_for_minutes(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "lap bien ban",
            "tao bien ban",
            "soan bien ban",
            "chuan bi bien ban",
            "bien ban vi pham",
            "bien ban danh gia",
        )
    )


def _asks_for_ticket(text: str) -> bool:
    return any(phrase in text for phrase in ("tao phieu", "lap phieu", "preview phieu", "phieu phap che"))


def _asks_to_send_legal(text: str) -> bool:
    return any(phrase in text for phrase in ("gui phap che", "chuyen phap che", "submit phap che"))


def _fold(text: str) -> str:
    table = str.maketrans(
        {
            "à": "a",
            "á": "a",
            "ả": "a",
            "ã": "a",
            "ạ": "a",
            "ă": "a",
            "ằ": "a",
            "ắ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "ặ": "a",
            "â": "a",
            "ầ": "a",
            "ấ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ậ": "a",
            "è": "e",
            "é": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ẹ": "e",
            "ê": "e",
            "ề": "e",
            "ế": "e",
            "ể": "e",
            "ễ": "e",
            "ệ": "e",
            "ì": "i",
            "í": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ị": "i",
            "ò": "o",
            "ó": "o",
            "ỏ": "o",
            "õ": "o",
            "ọ": "o",
            "ô": "o",
            "ồ": "o",
            "ố": "o",
            "ổ": "o",
            "ỗ": "o",
            "ộ": "o",
            "ơ": "o",
            "ờ": "o",
            "ớ": "o",
            "ở": "o",
            "ỡ": "o",
            "ợ": "o",
            "ù": "u",
            "ú": "u",
            "ủ": "u",
            "ũ": "u",
            "ụ": "u",
            "ư": "u",
            "ừ": "u",
            "ứ": "u",
            "ử": "u",
            "ữ": "u",
            "ự": "u",
            "ỳ": "y",
            "ý": "y",
            "ỷ": "y",
            "ỹ": "y",
            "ỵ": "y",
            "đ": "d",
        }
    )
    return text.casefold().translate(table)


def _reads(
    decision: ClarifyDecision,
    ignored: list[str],
    ambiguous: list[str],
    allowed_keys: set[str],
    locked_keys: set[str],
) -> list[_Read]:
    corrected = {item.key for item in decision.corrections}
    reads = []
    for item in (*decision.corrections, *decision.extracted_facts):
        if item.key in corrected and item not in decision.corrections:
            continue
        read = _read(item, ignored, ambiguous, allowed_keys, locked_keys)
        if read is not None:
            reads.append(read)
    return reads


def _read(
    item: ExtractedFact,
    ignored: list[str],
    ambiguous: list[str],
    allowed_keys: set[str],
    locked_keys: set[str],
) -> _Read | None:
    key = normalize_dynamic_key(item.key)
    amendment = bool(locked_keys and key not in locked_keys and key in _CRITICAL_AMENDMENT_KEYS)
    if not safe_dynamic_key(key) or _blocked_dynamic_key(key) or (key not in allowed_keys and not amendment):
        if key:
            ignored.append(key)
        return None
    if item.ambiguous or item.confidence < _MIN_FACT_CONFIDENCE:
        ambiguous.append(key)
        return None
    value = canonicalize(key, item.value, item.evidence)
    if value is None:
        ambiguous.append(key)
        return None
    return _Read(key, value, item.evidence.strip(), confirmed=not amendment)


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
    merged[item.key] = StoredFact(item.value, item.confirmed)
    conflicts[:] = [conflict for conflict in conflicts if conflict.key != item.key]


def _accept_present(
    family: str,
    merged: dict[str, StoredFact],
    conflicts: list[FactConflict],
    specs: tuple[FactSpec, ...],
) -> None:
    """A filled fact is the working value. The chat does not wait for a separate confirmation."""
    blocked = {conflict.key for conflict in conflicts}
    for spec in specs:
        if not spec.required:
            continue
        if spec.source == "amendment":
            continue
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
        family = _family_value(decision.family)
        return family if safe_dynamic_key(family) else GENERAL
    return _implied_keys(keys) or _implied(stored) or GENERAL


def _family_value(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        return GENERAL
    key = normalize_dynamic_key(raw)
    catalog = {ABSENCE, LATE, GENERAL}
    return raw if raw in catalog else key or GENERAL


def _schema_specs(
    family: str,
    decision: ClarifyDecision,
    stored: dict[str, StoredFact],
    reads: list[_Read],
    ignored: list[str],
    locked_keys: set[str],
) -> tuple[FactSpec, ...]:
    """Validate AI-proposed requirements and preserve catalog fallback behavior."""
    specs: list[FactSpec] = []
    seen: set[str] = set()
    for item in decision.fact_requirements:
        key = normalize_dynamic_key(item.key)
        if not safe_dynamic_key(key) or _blocked_dynamic_key(key):
            if key:
                ignored.append(key)
            continue
        if locked_keys and key not in locked_keys and key not in _CRITICAL_AMENDMENT_KEYS:
            ignored.append(key)
            continue
        label = _clean_label(item.label) or fact_label(key)
        question = _clean_question(item.question, label)
        source = "amendment" if locked_keys and key not in locked_keys else item.source or "ai_generated"
        specs.append(
            FactSpec(
                key=key,
                label=label,
                question=question,
                required=bool(item.required),
                source=source,
            )
        )
        seen.add(key)
    for key in sorted(locked_keys):
        if key in seen:
            continue
        specs.append(
            FactSpec(
                key=key,
                label=fact_label(key),
                question=f"Hãy bổ sung tình tiết {fact_label(key)}?",
                required=True,
                source="memory",
            )
        )
        seen.add(key)
    if not specs:
        specs.extend(default_dynamic_specs(family, set(stored)))
        seen.update(spec.key for spec in specs)
    for key in [*stored.keys(), *(item.key for item in reads)]:
        if key in seen or key in catalog_keys() or key == "":
            continue
        if locked_keys and key not in locked_keys:
            ignored.append(key)
            continue
        if not safe_dynamic_key(key) or _blocked_dynamic_key(key):
            ignored.append(key)
            continue
        specs.append(
            FactSpec(
                key=key,
                label=fact_label(key),
                question=f"Hãy bổ sung tình tiết {fact_label(key)}?",
                required=key in _CRITICAL_AMENDMENT_KEYS,
                source="amendment" if key in _CRITICAL_AMENDMENT_KEYS else "stored",
            )
        )
        seen.add(key)
    return tuple(specs)


def _blocked_dynamic_key(key: str) -> bool:
    return bool(_BLOCKED_DYNAMIC_WORDS.search(key))


def _clean_label(value: str) -> str:
    label = " ".join((value or "").split())
    if not label or len(label) > 80 or "\n" in label:
        return ""
    return label


def _clean_question(value: str, label: str) -> str:
    question = " ".join((value or "").split())
    if len(question) < 8 or len(question) > 240:
        return f"Hãy bổ sung {label}?"
    return question


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
    if len(raw) < 1 or len(raw) > 800:
        return None
    return raw


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
