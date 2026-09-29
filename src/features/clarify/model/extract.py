"""Pull fact values out of a Vietnamese narrative. Confirmed facts are not touched here."""

import re

from src.features.clarify.model.catalog import required_specs

_LINE = re.compile(r"(?im)^\s*([a-z_]+)\s*[:=]\s*(.+?)\s*$")
_ABSENCE = re.compile(
    r"(\d+\s*ngày(?:\s+trong(?:\s+vòng)?\s+(?:\d+\s*ngày|một tháng|1 tháng|365\s*ngày|một năm|12\s*tháng))?)",
    re.IGNORECASE,
)
_LATE = re.compile(r"(\d+\s*(?:ngày|lần))", re.IGNORECASE)
_CONTRACTS = (
    ("không xác định thời hạn", "không xác định thời hạn"),
    ("xác định thời hạn", "xác định thời hạn"),
    ("mùa vụ", "mùa vụ"),
    ("thử việc", "thử việc"),
)
_FLAG_KEYS = frozenset({"minutes_made", "explanation_requested"})
_YES = frozenset({"true", "yes", "1", "có", "co", "đã", "da", "rồi", "roi", "đúng", "dung"})
_NO = frozenset({"false", "no", "0", "không", "khong", "chưa", "chua", "không có", "chưa có"})


def extract_facts(family: str, text: str) -> dict[str, str]:
    """Return only keys this family asks for. An explicit ``key: value`` line wins."""
    keys = {spec.key for spec in required_specs(family)}
    found = _explicit(text, keys)
    for key, extractor in _heuristics(family).items():
        if key in found:
            continue
        value = extractor(text)
        if value:
            found[key] = value
    return {key: _normalize(key, value) for key, value in found.items()}


def is_yes(value: str) -> bool:
    """True when a stored flag says the step already happened."""
    text = value.strip().casefold()
    return text in _YES or text.startswith("đã ") or text.startswith("da ")


def is_no(value: str) -> bool:
    """True when a stored flag says the step has not happened."""
    text = value.strip().casefold()
    if text in _NO or text.startswith("chưa") or text.startswith("chua"):
        return True
    return text.startswith("không") or text.startswith("khong")


def _explicit(text: str, keys: set[str]) -> dict[str, str]:
    found = {}
    for match in _LINE.finditer(text):
        key = match.group(1)
        if key in keys:
            found[key] = match.group(2).strip()
    return found


def _heuristics(family: str) -> dict[str, object]:
    shared = {
        "contract_type": _contract,
        "minutes_made": _minutes,
        "explanation_requested": _explanation,
        "notice_form": _notice,
        "absence_days": _absence,
        "late_days": _late_count,
        "violation_summary": _summary,
    }
    keys = {spec.key for spec in required_specs(family)}
    return {key: shared[key] for key in keys if key in shared}


def _normalize(key: str, value: str) -> str:
    if key not in _FLAG_KEYS:
        return value
    flag = _flag(value)
    return flag if flag is not None else value


def _flag(value: str) -> str | None:
    text = value.strip().casefold()
    if "chưa" in text or "chua" in text or text in _NO or text.startswith("không") or text.startswith("khong"):
        return "false"
    if text in _YES or text.startswith("đã") or text.startswith("da"):
        return "true"
    return None


def _contract(text: str) -> str | None:
    folded = text.casefold()
    for needle, label in _CONTRACTS:
        if needle in folded:
            return label
    return None


def _minutes(text: str) -> str | None:
    folded = text.casefold()
    if "chưa lập biên bản" in folded or "chưa có biên bản" in folded:
        return "false"
    if "đã lập biên bản" in folded or "có biên bản" in folded:
        return "true"
    return None


def _explanation(text: str) -> str | None:
    folded = text.casefold()
    if "chưa yêu cầu giải trình" in folded or "chưa gửi yêu cầu giải trình" in folded:
        return "false"
    if "đã yêu cầu giải trình" in folded or "đã gửi yêu cầu giải trình" in folded:
        return "true"
    return None


def _notice(text: str) -> str | None:
    folded = text.casefold()
    if "không báo" in folded or "không xin" in folded:
        return "không báo"
    if "điện thoại" in folded or "gọi điện" in folded:
        return "điện thoại"
    if "tin nhắn" in folded or "zalo" in folded:
        return "tin nhắn"
    if "email" in folded or "thư điện tử" in folded:
        return "email"
    if "nộp đơn" in folded or "gửi đơn" in folded or "bằng đơn" in folded:
        return "đơn"
    if "trực tiếp" in folded:
        return "trực tiếp"
    return None


def _absence(text: str) -> str | None:
    match = _ABSENCE.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _late_count(text: str) -> str | None:
    match = _LATE.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _summary(text: str) -> str | None:
    match = re.search(r"vi phạm\s+(.{8,180}?)(?:\.|$)", text, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).strip()
