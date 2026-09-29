"""Decide which facts are still missing and which question to ask next."""

from dataclasses import dataclass

from src.features.clarify.model.catalog import detect_family, required_specs
from src.features.clarify.model.extract import extract_facts


@dataclass(frozen=True)
class StoredFact:
    """A fact already kept on the case."""

    value: str
    confirmed: bool


@dataclass(frozen=True)
class ClarifyPlan:
    """What extract and ask decided for one turn."""

    family: str
    merged: dict[str, StoredFact]
    missing_keys: list[str]
    locked: bool
    question: str = ""


def assess(text: str, stored: dict[str, StoredFact]) -> ClarifyPlan:
    """Merge newly read values into stored facts. A confirmed value is left as it is."""
    family = detect_family(text)
    merged = _merge(stored, extract_facts(family, text))
    missing = _missing(family, merged)
    locked = not missing and _all_confirmed(family, merged)
    return ClarifyPlan(family=family, merged=merged, missing_keys=missing, locked=locked)


def build_question(family: str, missing: list[str], merged: dict[str, StoredFact]) -> str:
    """Ask for the first missing fact, or list the values still waiting for confirmation."""
    specs = required_specs(family)
    if missing:
        spec = next(item for item in specs if item.key == missing[0])
        tail = f" Còn {len(missing) - 1} mục sẽ hỏi sau." if len(missing) > 1 else ""
        return spec.question + tail
    lines = [f"- {spec.label}: {merged[spec.key].value}" for spec in specs if _pending(merged, spec.key)]
    listed = "\n".join(lines)
    return (
        "Đã đủ tình tiết nhưng chưa được xác nhận. "
        "Hãy sửa nếu cần, rồi xác nhận từng dòng. Chưa đối chiếu văn bản và chưa chốt mức kỷ luật.\n"
        f"{listed}"
    )


def _merge(stored: dict[str, StoredFact], found: dict[str, str]) -> dict[str, StoredFact]:
    merged = dict(stored)
    for key, value in found.items():
        current = merged.get(key)
        if current is not None and current.confirmed:
            continue
        merged[key] = StoredFact(value=value, confirmed=False)
    return merged


def _missing(family: str, merged: dict[str, StoredFact]) -> list[str]:
    missing = []
    for spec in required_specs(family):
        item = merged.get(spec.key)
        if item is None or not item.value.strip():
            missing.append(spec.key)
    return missing


def _all_confirmed(family: str, merged: dict[str, StoredFact]) -> bool:
    return all(merged[spec.key].confirmed for spec in required_specs(family))


def _pending(merged: dict[str, StoredFact], key: str) -> bool:
    item = merged.get(key)
    return item is not None and not item.confirmed
