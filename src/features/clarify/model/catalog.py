"""Required facts for each kind of case the chat knows how to clarify."""

import re
from dataclasses import dataclass

ABSENCE = "UNAUTHORIZED_ABSENCE"
LATE = "LATE"
GENERAL = "GENERAL"

_ABSENCE_MARKERS = ("nghỉ không phép", "không phép", "tự ý nghỉ", "tự ý bỏ việc")
_LATE_MARKERS = ("đi muộn", "đi trễ", "trễ giờ", "muộn giờ")


@dataclass(frozen=True)
class FactSpec:
    """One fact the recommender is not allowed to guess."""

    key: str
    label: str
    question: str
    required: bool = True
    source: str = "catalog"


_ABSENCE = (
    FactSpec(
        "contract_type",
        "Loại hợp đồng",
        "Hợp đồng của nhân viên là loại nào: thử việc, xác định thời hạn, không xác định thời hạn, hay mùa vụ?",
    ),
    FactSpec(
        "absence_days",
        "Số ngày nghỉ không phép",
        "Nhân viên nghỉ không phép bao nhiêu ngày, và các ngày đó nằm trong 30 ngày hay trong 365 ngày gần nhất?",
    ),
    FactSpec(
        "notice_form",
        "Hình thức báo vắng",
        "Nhân viên đã báo vắng bằng hình thức nào, hay không báo?",
    ),
    FactSpec("minutes_made", "Đã lập biên bản", "Đã lập biên bản vi phạm chưa?"),
    FactSpec(
        "explanation_requested",
        "Đã yêu cầu giải trình",
        "Đã gửi yêu cầu giải trình cho nhân viên chưa?",
    ),
)

_LATE = (
    _ABSENCE[0],
    FactSpec(
        "late_days",
        "Số lần hoặc số ngày đi muộn",
        "Nhân viên đi muộn bao nhiêu ngày hoặc bao nhiêu lần trong kỳ đang xét?",
    ),
    _ABSENCE[3],
    _ABSENCE[4],
)

_GENERAL = (
    _ABSENCE[0],
    FactSpec(
        "violation_summary",
        "Hành vi vi phạm",
        "Mô tả ngắn hành vi cần đối chiếu, trong một hoặc hai câu?",
    ),
    _ABSENCE[3],
    _ABSENCE[4],
)

_SPECS = {ABSENCE: _ABSENCE, LATE: _LATE, GENERAL: _GENERAL}

# Observed from prior decisions. It is not required to lock a case, and it stays
# out of the assessment until HR confirms it.
OPTIONAL_FACT_KEYS = frozenset({"prior_sanction_count"})


def detect_family(text: str) -> str:
    """Pick the fact set from the narrative. Absence wins over lateness."""
    folded = text.casefold()
    if any(marker in folded for marker in _ABSENCE_MARKERS):
        return ABSENCE
    if any(marker in folded for marker in _LATE_MARKERS):
        return LATE
    return GENERAL


def resolved_family(description: str, stored: str | None) -> str:
    """Use the narrative when it names a family. Otherwise keep the stored family."""
    detected = detect_family(description or "")
    if detected != GENERAL:
        return detected
    if stored in _SPECS:
        return stored
    return GENERAL


def fact_label(key: str) -> str:
    """Vietnamese label for a catalog fact. An unknown key is returned as stored."""
    for specs in _SPECS.values():
        for spec in specs:
            if spec.key == key:
                return spec.label
    return key


def required_specs(family: str) -> tuple[FactSpec, ...]:
    """Return the fact set. An unknown family uses the general set."""
    return _SPECS.get(family, _SPECS[GENERAL])


def normalize_dynamic_key(value: str) -> str:
    """Return a safe snake_case key for AI-proposed facts."""
    key = re.sub(r"[^a-z0-9_]+", "_", value.casefold().strip())
    key = re.sub(r"_+", "_", key).strip("_")
    return key[:80]


def safe_dynamic_key(value: str) -> bool:
    """Dynamic fact keys are data identifiers, not instructions or prose."""
    key = normalize_dynamic_key(value)
    return bool(key) and bool(re.fullmatch(r"[a-z][a-z0-9_]{1,79}", key))


def default_dynamic_specs(family: str, stored_keys: set[str] | None = None) -> tuple[FactSpec, ...]:
    """Catalog specs plus any stored custom facts so older cases remain readable."""
    specs = list(required_specs(family))
    known = {spec.key for spec in specs}
    for key in sorted(stored_keys or set()):
        if key in known or key in OPTIONAL_FACT_KEYS or not safe_dynamic_key(key):
            continue
        specs.append(FactSpec(key=key, label=fact_label(key), question=f"Hãy bổ sung tình tiết {fact_label(key)}?"))
        known.add(key)
    return tuple(specs)


def catalog_keys() -> set[str]:
    """Every fact key a family can require. The planner may not invent keys outside this set."""
    keys: set[str] = set()
    for specs in _SPECS.values():
        keys.update(spec.key for spec in specs)
    keys.update(OPTIONAL_FACT_KEYS)
    return keys


def fact_lines(family: str, facts: dict[str, str], specs: tuple[FactSpec, ...] | None = None) -> list[str]:
    """Label confirmed values in catalog order for the answer and the search text."""
    lines = []
    used = set()
    for spec in specs or required_specs(family):
        value = facts.get(spec.key)
        if value:
            lines.append(f"{spec.label}: {value}")
            used.add(spec.key)
    prior = facts.get("prior_sanction_count")
    if prior:
        lines.append(f"Số lần đã bị xử lý trước: {prior}")
        used.add("prior_sanction_count")
    for key, value in sorted(facts.items()):
        if key in used or not value:
            continue
        lines.append(f"{fact_label(key)}: {value}")
    return lines
