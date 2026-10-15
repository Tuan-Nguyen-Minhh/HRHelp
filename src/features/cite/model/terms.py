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
_LIMIT = 48
_PHRASES = (
    "mã nguồn", "tiết lộ", "bí mật kinh doanh", "bí mật công nghệ", "thông tin mật",
    "kiến trúc phần mềm", "đối thủ", "bên thứ ba", "dữ liệu khách hàng",
    "nghỉ không phép", "tự ý bỏ việc", "đi muộn", "đi trễ", "an toàn lao động",
    "quấy rối", "trộm cắp", "thiệt hại", "tái phạm",
)


def hint_for(family: str) -> str:
    """Legal words added so a short fact line can still find the right article."""
    return _HINTS.get(family, _HINTS[GENERAL])


def search_terms(family: str, fact_lines: list[str], description: str) -> list[str]:
    """Conduct phrases first; background facts cannot consume the query budget."""
    background = ("hợp đồng", "biên bản", "giải trình", "mã nhân viên", "tên nhân viên", "bộ phận", "chức danh")
    relevant = [line for line in fact_lines if not any(word in line.partition(":")[0].casefold() for word in background)]
    text = " ".join([*relevant, description, hint_for(family)]).casefold()
    terms: list[str] = [phrase for phrase in _PHRASES if phrase in text]
    seen: set[str] = set(terms)
    for token in _TOKEN.findall(text.casefold()):
        if len(token) < 3 or token in _STOP or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) == _LIMIT:
            break
    return terms
