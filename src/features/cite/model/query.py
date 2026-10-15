"""Input of one policy search."""

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class SearchQuery:
    """What the retrieve node asks the corpus."""

    text: str
    incident_date: date
    agent_run_id: UUID
    family: str
    fact_lines: list[str]
    description: str
    embedding: tuple[float, ...] | None = None


_BACKGROUND = ("hợp đồng", "biên bản", "giải trình", "mã nhân viên", "tên nhân viên", "bộ phận", "chức danh")
_PLACEHOLDER = re.compile(r"^(của )?(nhân viên|người lao động)( này)?[.! ]*$", re.IGNORECASE)


def act_text(query: SearchQuery) -> str:
    """Keep the conduct/object/recipient ahead of contract and workflow facts."""
    conduct = []
    for line in query.fact_lines:
        label, _, value = line.partition(":")
        if any(word in label.casefold() for word in _BACKGROUND):
            continue
        if value.strip() and not _PLACEHOLDER.fullmatch(value.strip()):
            conduct.append(line.strip())
    description = query.description.strip()
    if description and not _PLACEHOLDER.fullmatch(description):
        conduct.append(description)
    if not conduct:
        conduct.append(query.text.strip())
    return "\n".join(dict.fromkeys(part for part in conduct if part))


def facet_queries(query: SearchQuery) -> dict[str, str]:
    """Search needs, not fabricated case facts or a desired sanction."""
    act = act_text(query)
    return {
        "internal_rule": f"{act}\nNội quy: hành vi và hình thức xử lý áp dụng, điều kiện của từng mức.",
        "authority": f"{act}\nPháp luật và hướng dẫn: điều kiện áp dụng hình thức xử lý đối với hành vi này.",
        "conditions": f"{act}\nĐịnh nghĩa, điều kiện, ngoại lệ, trường hợp không được xử lý đối với hành vi này.",
        "procedure": f"{act}\nTrình tự, thủ tục, thời hiệu, thẩm quyền xử lý kỷ luật lao động.",
    }
