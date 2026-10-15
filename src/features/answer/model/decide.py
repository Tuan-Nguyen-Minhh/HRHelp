"""Choose a sanction only from locked facts and a guarded synthesis assessment.

Sa thải (DISMISSAL) and chấm dứt hợp đồng (TERMINATION) are different grounds.
This module never returns TERMINATION. It does not read a level out of the
passage text. The synthesis assessment is the only source of a level.
"""

from dataclasses import dataclass

from src.features.answer.model.assessment import Assessment
from src.features.answer.model.layers import LayeredBasis
from src.features.answer.schema import SANCTION_LABELS, ProcessStep
from src.features.clarify.model.extract import is_yes


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
    """Everything the comparison needs. The prose renderer is separate."""

    family: str
    facts: dict[str, str]
    layered: LayeredBasis
    retrieval: str = "hybrid"
    description: str = ""
    fact_lines: tuple[str, ...] = ()


def decide(data: DecisionInput, assessment: Assessment | None = None) -> SanctionDecision:
    """Return the guarded assessment level, or leave the level open."""
    steps = process_steps(data.facts)
    missing_rule = data.layered.missing_internal_rule
    opened = _blocked(data, steps, missing_rule)
    if opened is not None:
        return _mention_report_level(opened, assessment)
    if assessment is None or not assessment.downstream_handoff.can_recommend:
        reason = assessment.sanction_assessment.reason if assessment is not None else _NO_SYNTHESIS
        multiple = assessment is not None and assessment.sanction_assessment.status == "MULTIPLE_SUPPORTED"
        return _open(steps, "MEDIUM" if multiple else "HIGH", reason, missing_rule)
    level = assessment.sanction_assessment.recommended_sanction
    if not level or level == "TERMINATION":
        return _open(steps, "HIGH", _NO_SYNTHESIS, missing_rule)
    reason = assessment.sanction_assessment.reason
    if level == "DISMISSAL" and "TERMINATION" not in reason:
        reason = f"{reason} Không đề xuất chấm dứt hợp đồng (TERMINATION)."
    return _locked(steps, level, assessment.risk_assessment.level, reason, missing_rule)


def blocked(data: DecisionInput) -> SanctionDecision | None:
    """Return the open lock when this case must not store a company level."""
    return _blocked(data, process_steps(data.facts), data.layered.missing_internal_rule)


def should_synthesize(data: DecisionInput) -> bool:
    """Ask the model when a law, guiding decree, or internal rule was retrieved.

    A page-index hit, an empty corpus, or only an administrative-penalty passage
    stays in Python. Missing minutes, a missing companion source, or probation
    does not skip the report: those limits stay in the lock, not in the reading.
    """
    if data.retrieval == "page_index":
        return False
    return bool(data.layered.legal_basis or data.layered.internal_rule)


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


def _blocked(data: DecisionInput, steps: list[ProcessStep], missing_rule: bool) -> SanctionDecision | None:
    if data.retrieval == "page_index":
        return _open(steps, "HIGH", _PAGE_INDEX, missing_rule)
    if _no_applicable_layer(data.layered):
        if data.layered.inspection_risk:
            return _open(steps, "HIGH", _INSPECTION, True)
        return _open(steps, "CRITICAL", _EMPTY, True)
    if not data.layered.legal_basis:
        return _open(steps, "HIGH", _NO_LAW, missing_rule)
    if missing_rule:
        return _open(steps, "HIGH", _NO_RULE, True)
    return None


def _open(steps: list[ProcessStep], risk: str, reason: str, missing_rule: bool) -> SanctionDecision:
    return SanctionDecision(None, risk, reason, steps, missing_rule)


def _locked(steps: list[ProcessStep], level: str, risk: str, reason: str, missing_rule: bool) -> SanctionDecision:
    return SanctionDecision(level, risk, reason, steps, missing_rule)


def _mention_report_level(opened: SanctionDecision, assessment: Assessment | None) -> SanctionDecision:
    """Keep a reported company level visible without locking it for issue."""
    if assessment is None:
        return opened
    level = assessment.sanction_assessment.recommended_sanction
    if not level or level == "TERMINATION" or level not in SANCTION_LABELS:
        return opened
    extra = f"Mức trong biên bản: {SANCTION_LABELS[level]}. Mức này chưa được khóa để ban hành."
    if extra in opened.rationale:
        return opened
    return SanctionDecision(
        None,
        opened.risk_level,
        f"{opened.rationale} {extra}",
        opened.process_steps,
        opened.missing_internal_rule,
    )


def _no_applicable_layer(layered: LayeredBasis) -> bool:
    return not layered.legal_basis and not layered.internal_rule and not layered.precedent


_EMPTY = "Kho văn bản không có đoạn nào còn hiệu lực vào ngày xảy ra việc. Chưa đủ căn cứ để chốt mức."
_INSPECTION = "Chỉ thấy nghị định xử phạt hành chính. Đó là cảnh báo thanh tra, không phải mức kỷ luật để công ty chọn."
_NO_RULE = (
    "Đã có đoạn luật hoặc nghị định. Chưa có nội quy còn hiệu lực vào ngày xảy ra việc, nên chưa khóa mức công ty."
)
_NO_LAW = (
    "Biên bản ghi mức theo nội quy khi điều khoản khớp. "
    "Chưa retrieval được luật hoặc nghị định hướng dẫn cho cùng hành vi, nên chưa khóa mức để ban hành."
)
_PAGE_INDEX = "Chỉ tìm được đầu điều từ mục lục. Chưa đủ nội dung điều khoản để xác định mức kỷ luật."
_NO_SYNTHESIS = "Chưa có bản tổng hợp bám đoạn đã retrieval. Mức xử lý đề xuất: chưa xác định."
