"""Turn a case narrative into a short list of search terms."""

import re

from src.features.clarify.model.catalog import ABSENCE, GENERAL, LATE

_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOP = frozenset(
    {
        "của",
        "và",
        "cho",
        "với",
        "một",
        "các",
        "được",
        "trong",
        "ngày",
        "nhân",
        "viên",
        "đã",
        "chưa",
        "không",
        "này",
        "khi",
        "theo",
        "hoặc",
        "nhưng",
        "về",
        "là",
        "có",
        "các",
        "để",
        "nên",
        "vẫn",
    }
)
_HINTS = {
    ABSENCE: "kỷ luật sa thải nghỉ không phép tự ý bỏ việc",
    LATE: "kỷ luật đi muộn nội quy lao động",
    GENERAL: "xử lý kỷ luật lao động nội quy",
}
_LIMIT = 12


def hint_for(family: str) -> str:
    """Legal words added so a short fact line can still find the right article."""
    return _HINTS.get(family, _HINTS[GENERAL])


def search_terms(family: str, fact_lines: list[str], description: str) -> list[str]:
    """Hints first, then facts, then the description. At most twelve terms."""
    text = " ".join([hint_for(family), *fact_lines, description])
    terms: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN.findall(text.casefold()):
        if len(token) < 3 or token in _STOP or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) == _LIMIT:
            break
    return terms
