"""Choose a sanction only from locked facts and the layers that may support one.

Sa thải (DISMISSAL) and chấm dứt hợp đồng (TERMINATION) are different grounds.
This module never returns TERMINATION.
"""

import re
from dataclasses import dataclass

from src.features.answer.model.layers import LayeredBasis
from src.features.answer.schema import SANCTION_LABELS, ProcessStep
from src.features.clarify.model.catalog import ABSENCE
from src.features.clarify.model.extract import is_yes

_LEVELS = (
    ("WAGE_POSTPONEMENT", ("kéo dài thời hạn nâng lương", "kéo dài nâng lương", "hoãn nâng lương")),
    ("DISMISSAL", ("sa thải",)),
    ("DEMOTION", ("cách chức",)),
    ("REPRIMAND", ("cảnh cáo",)),
    ("WARNING", ("khiển trách",)),
)
_DISMISSAL_ACTS = ("không phép", "tự ý", "bỏ việc")


@dataclass(frozen=True)
class SanctionDecision:
    """The proposal columns, before they are written to ``recommendations``."""

    sanction_type: str | None
    risk_level: str
    rationale: str
    process_steps: list[ProcessStep]
    missing_internal_rule: bool


@dataclass(frozen=True)
class DecisionInput:
    """Everything the rule needs. The prose renderer is separate."""

    family: str
    facts: dict[str, str]
    layered: LayeredBasis


def decide(data: DecisionInput) -> SanctionDecision:
    """Return a level, or leave it open and raise the risk instead."""
    steps = process_steps(data.facts)
    missing_rule = data.layered.missing_internal_rule
    opened = _blocked(data, steps, missing_rule)
    if opened is not None:
        return opened
    return _from_rules(data, steps, missing_rule)


def process_steps(facts: dict[str, str]) -> list[ProcessStep]:
    """The procedure the answer always shows, whether or not a level is locked."""
    return [
        ProcessStep(code="MINUTES", label="Lập biên bản vi phạm", done=is_yes(facts.get("minutes_made", ""))),
        ProcessStep(
            code="EXPLANATION_REQUEST",
            label="Gửi yêu cầu giải trình",
            done=is_yes(facts.get("explanation_requested", "")),
        ),
        ProcessStep(code="TIME_LIMIT", label="Kiểm tra thời hiệu xử lý kỷ luật", done=False),
        ProcessStep(code="SIGNER", label="Người có thẩm quyền ban hành quyết định", done=False),
    ]


def absence_meets_dismissal(text: str) -> bool:
    """True for 5 days inside 30, or 20 days inside 365. The window must be in the fact."""
    days = _absence_days(text)
    window = _window(text)
    if days is None or window is None:
        return False
    if window == 30:
        return days >= 5
    return days >= 20


def _blocked(data: DecisionInput, steps: list[ProcessStep], missing_rule: bool) -> SanctionDecision | None:
    if _no_applicable_layer(data.layered):
        if data.layered.inspection_risk:
            return _open(steps, "HIGH", _INSPECTION, True)
        return _open(steps, "CRITICAL", _EMPTY, True)
    if _probation(data.facts.get("contract_type", "")):
        return _open(steps, "HIGH", _PROBATION, missing_rule)
    if not _procedure_ready(data.facts):
        return _open(steps, "HIGH", _PROCEDURE, missing_rule)
    if missing_rule:
        return _open(steps, "HIGH", _NO_RULE, True)
    if data.family == ABSENCE and _window_missing(data.facts.get("absence_days", "")):
        return _open(steps, "HIGH", _WINDOW, False)
    return None


def _from_rules(data: DecisionInput, steps: list[ProcessStep], missing_rule: bool) -> SanctionDecision:
    if data.family == ABSENCE and absence_meets_dismissal(data.facts.get("absence_days", "")):
        if _rule_allows_dismissal(data.layered):
            return _locked(steps, "DISMISSAL", "MEDIUM", _DISMISSAL, missing_rule)
        return _open(steps, "HIGH", _DISMISSAL_UNSTATED, missing_rule)
    level = _single_company_level(data.layered)
    if level is None:
        return _open(steps, "MEDIUM", _UNCLEAR, missing_rule)
    reason = f"Nội quy đang hiệu lực chỉ nêu một mức: {_label(level)}. Đây là đề xuất để HR xem, chưa phải quyết định."
    return _locked(steps, level, "MEDIUM", reason, missing_rule)


def _open(steps: list[ProcessStep], risk: str, reason: str, missing_rule: bool) -> SanctionDecision:
    return SanctionDecision(None, risk, reason, steps, missing_rule)


def _locked(steps: list[ProcessStep], level: str, risk: str, reason: str, missing_rule: bool) -> SanctionDecision:
    return SanctionDecision(level, risk, reason, steps, missing_rule)


def _no_applicable_layer(layered: LayeredBasis) -> bool:
    return not layered.legal_basis and not layered.internal_rule and not layered.precedent


def _probation(contract: str) -> bool:
    return "thử việc" in contract.casefold()


def _procedure_ready(facts: dict[str, str]) -> bool:
    return is_yes(facts.get("minutes_made", "")) and is_yes(facts.get("explanation_requested", ""))


def _window_missing(text: str) -> bool:
    days = _absence_days(text)
    return days is not None and days >= 5 and _window(text) is None


def _absence_days(text: str) -> int | None:
    counts = [int(item) for item in re.findall(r"(\d+)\s*ngày", text.casefold())]
    counts = [item for item in counts if item not in {30, 365}]
    if not counts:
        return None
    return counts[0]


def _window(text: str) -> int | None:
    folded = text.casefold()
    if re.search(r"365\s*ngày|một năm|12\s*tháng", folded):
        return 365
    if re.search(r"trong(?:\s+vòng)?\s+30\s*ngày|trong(?:\s+vòng)?\s+một tháng|trong(?:\s+vòng)?\s+1\s*tháng", folded):
        return 30
    return None


def _rule_allows_dismissal(layered: LayeredBasis) -> bool:
    for passage in layered.internal_rule:
        text = passage.content.casefold()
        if "sa thải" in text and any(token in text for token in _DISMISSAL_ACTS):
            return True
    return False


def _single_company_level(layered: LayeredBasis) -> str | None:
    """One company level, never sa thải. Sa thải is decided only on the absence rule."""
    found: set[str] = set()
    for passage in layered.internal_rule:
        found.update(_levels_in(passage.content))
    if "DISMISSAL" in found or len(found) != 1:
        return None
    return next(iter(found))


def _levels_in(content: str) -> set[str]:
    folded = content.casefold()
    return {level for level, phrases in _LEVELS if any(phrase in folded for phrase in phrases)}


def _label(level: str) -> str:
    return SANCTION_LABELS[level]


_EMPTY = "Kho văn bản không có đoạn nào còn hiệu lực vào ngày xảy ra việc. Chưa đủ căn cứ để chốt mức."
_INSPECTION = "Chỉ thấy nghị định xử phạt hành chính. Đó là cảnh báo thanh tra, không phải mức kỷ luật để công ty chọn."
_PROBATION = "Hợp đồng đang trong thời gian thử việc. Không đề xuất sa thải hay chấm dứt hợp đồng từ fact này."
_PROCEDURE = "Chưa lập biên bản hoặc chưa gửi yêu cầu giải trình. Chưa chốt mức khi thủ tục còn thiếu."
_NO_RULE = (
    "Đã có căn cứ luật nhưng chưa có nội quy nội bộ còn hiệu lực vào ngày xảy ra việc. Chưa chốt mức công ty được dùng."
)
_WINDOW = "Số ngày nghỉ đã từ 5 nhưng fact chưa khóa khoảng 30 ngày hay 365 ngày. Chưa chốt sa thải."
_DISMISSAL = (
    "Fact đã khóa khớp ngưỡng sa thải của luật và nội quy đang hiệu lực có điều khoản sa thải cho nghỉ không phép. "
    "Mức đề xuất là sa thải (DISMISSAL). Không đề xuất chấm dứt hợp đồng (TERMINATION), vì đó là căn cứ khác."
)
_DISMISSAL_UNSTATED = "Fact khớp ngưỡng sa thải của luật, nhưng đoạn nội quy lấy được không nêu sa thải đối với nghỉ không phép. Chưa chốt mức."
_UNCLEAR = (
    "Đã có luật và nội quy, thủ tục đã đủ, nhưng nội quy không nêu đúng một mức. "
    "HR chọn mức theo điều khoản nội quy được trích, không lấy mức từ nghị định xử phạt."
)
