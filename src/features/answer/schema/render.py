"""Vietnamese answer laid out in the four citation layers."""

from dataclasses import dataclass
from datetime import date

from src.common.text import clip_quote
from src.features.answer.model.decide import SanctionDecision
from src.features.answer.model.layers import LayeredBasis
from src.features.answer.model.standard import applied_standard
from src.features.answer.schema import SANCTION_LABELS
from src.features.cite.model.passage import Passage

HEADINGS = (
    "Chuẩn áp dụng",
    "Nhận định",
    "Mức chế tài",
    "Quy trình",
    "Mức rủi ro",
    "Căn cứ công ty được áp",
    "Mức nội quy đúng ngày",
    "Tiền lệ",
    "Cảnh báo thanh tra",
)
_EMPTY_LEGAL = "Không thấy điều luật hoặc nghị định hướng dẫn còn hiệu lực trong lượt đối chiếu này."
_EMPTY_INTERNAL = "Chưa có nội quy nội bộ còn hiệu lực vào ngày xảy ra việc, nên chưa chốt mức công ty được phép dùng."
_INSPECTION = "Nghị định xử phạt hành chính, gồm Nghị định 283, không phải mức kỷ luật để công ty chọn."


@dataclass(frozen=True)
class RenderInput:
    """Facts and layers already chosen. This module only writes the message."""

    employee_name: str | None
    incident_date: date
    fact_lines: list[str]
    decision: SanctionDecision
    layered: LayeredBasis
    precedent_note: str


def render(data: RenderInput) -> str:
    """Return the chat message HR reads."""
    sections = [
        _section(HEADINGS[0], _applied(data.decision)),
        _section(HEADINGS[1], _finding(data)),
        _section(HEADINGS[2], _sanction(data.decision)),
        _section(HEADINGS[3], _process(data.decision)),
        _section(HEADINGS[4], f"{data.decision.risk_level} — {data.decision.rationale}"),
        _section(HEADINGS[5], _quotes(data.layered.legal_basis, _EMPTY_LEGAL)),
        _section(HEADINGS[6], _quotes(data.layered.internal_rule, _EMPTY_INTERNAL)),
        _section(HEADINGS[7], _precedent(data)),
        _section(HEADINGS[8], _inspection(data.layered.inspection_risk)),
    ]
    return "\n\n".join(sections)


def _section(title: str, body: str) -> str:
    return f"{title}\n{body}"


def _finding(data: RenderInput) -> str:
    who = data.employee_name or "nhân viên"
    when = data.incident_date.strftime("%d/%m/%Y")
    lines = [f"Vụ của {who}, ngày xảy ra {when}."]
    lines.extend(data.fact_lines)
    lines.append(data.decision.rationale)
    return "\n".join(lines)


def _applied(decision: SanctionDecision) -> str:
    standard = applied_standard(decision.sanction_type, decision.risk_level, decision.process_steps)
    level = SANCTION_LABELS[standard.sanction_type] if standard.aligned and standard.sanction_type else "Chưa khóa để ban hành."
    steps = "; ".join(step.label for step in standard.process_steps)
    notes = "\n".join(f"- {item.note}" for item in standard.layers)
    return f"{standard.rule}\nMức: {level}\nQuy trình: {steps}\n{notes}"


def _sanction(decision: SanctionDecision) -> str:
    if decision.sanction_type is None:
        return decision.rationale or "Kết quả đánh giá nằm trong biên bản để HR xem."
    label = SANCTION_LABELS[decision.sanction_type]
    if decision.sanction_type == "DISMISSAL":
        return f"{label}. Không đề xuất chấm dứt hợp đồng (TERMINATION)."
    return label


def _process(decision: SanctionDecision) -> str:
    lines = []
    for index, step in enumerate(decision.process_steps, start=1):
        mark = "đã có" if step.done else "chưa có"
        lines.append(f"{index}. {step.label} ({mark})")
    return "\n".join(lines)


def _quotes(passages: list[Passage], empty: str) -> str:
    if not passages:
        return empty
    return "\n".join(_quote_line(passage) for passage in passages)


def _precedent(data: RenderInput) -> str:
    if not data.layered.precedent:
        return data.precedent_note
    return f"{data.precedent_note}\n{_quotes(data.layered.precedent, '')}"


def _inspection(passages: list[Passage]) -> str:
    if not passages:
        return f"{_INSPECTION} Lượt đối chiếu này không thấy đoạn nào thuộc nhóm đó."
    return f"{_INSPECTION}\n{_quotes(passages, '')}"


def _quote_line(passage: Passage) -> str:
    title = passage.policy_name or passage.policy_code
    place = _place(passage)
    prefix = f"{title} {place}".strip()
    return f'- {prefix}: "{clip_quote(passage.content)}"'


def _place(passage: Passage) -> str:
    parts = [
        _bit(passage.article, "điều", "Điều"),
        _bit(passage.clause, "khoản", "khoản"),
        _bit(passage.point, "điểm", "điểm"),
    ]
    return " ".join(part for part in parts if part)


def _bit(value: str | None, prefix: str, label: str) -> str:
    if not value:
        return ""
    if value.casefold().startswith(prefix):
        return value
    return f"{label} {value}"
