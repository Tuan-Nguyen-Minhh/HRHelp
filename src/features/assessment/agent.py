"""Assemble the assessment form from stored facts, citations, and the locked recommendation.

A second model call is not used. Citations and the company level come from rows
Python already checked. The prompt in ``prompts.py`` is the contract: this step
does not confirm the form and does not send a ticket.
"""

import re
from dataclasses import dataclass
from datetime import date

from src.features.answer.schema import AnswerView, CitationView
from src.features.assessment.schemas import (
    AssessmentResult,
    AssessmentSection,
    CaseInformation,
    ConfirmedFact,
    EmployeeInformation,
    EvidenceCard,
    HandlingProposal,
    IncidentSummary,
    MissingItem,
    NextStep,
    ProposedAction,
    RiskAndGaps,
    Sections,
)

_COMPANY = {
    "WARNING": "Khiển trách",
    "REPRIMAND": "Cảnh cáo",
    "WAGE_POSTPONEMENT": "Kéo dài thời hạn nâng lương",
    "DEMOTION": "Cách chức",
    "DISMISSAL": "Sa thải",
}
_CHUNK_ID_RE = re.compile(r"\s*-?\s*Chunk[_\s-]*id\s*:\s*[\w-]+", re.IGNORECASE)
_MARKDOWN_RE = re.compile(r"[*_`]+")
_ROMAN_HEADING_RE = re.compile(r"\b[IVXLCDM]{1,6}\.\s+[A-ZÀ-Ỹ][^.\n]*(?:\.|\s+-)?", re.IGNORECASE)
_INCIDENT_FACT_KEYS = {
    "absence_days",
    "late_days",
    "notice_form",
    "violation_time",
    "violation_place",
    "violation_description",
}


@dataclass(frozen=True)
class FactInput:
    key: str
    label: str
    value: str | None
    confirmed: bool
    required: bool


@dataclass(frozen=True)
class ComposeInput:
    case_code: str
    case_status: str
    family: str | None
    incident_date: date | None
    description: str
    employee_code: str | None
    employee_name: str | None
    facts: tuple[FactInput, ...]
    answer: AnswerView


def compose(source: ComposeInput) -> tuple[Sections, dict[str, str]]:
    """Build sections. Unknown sanctions and inspection text do not become a level."""
    facts = [_fact(item) for item in source.facts]
    cards = _cards(source.answer)
    missing = [
        MissingItem(fact_key=item.fact_key, reason=f"Chưa có {item.label}.", blocking=item.blocking)
        for item in facts
        if item.status == "MISSING" and item.blocking
    ]
    sanction = source.answer.sanction_type if source.answer.sanction_type in _COMPANY else None
    risk = source.answer.risk_level
    blocked = bool(missing)
    proposed = [ProposedAction(code=sanction, label=_COMPANY[sanction])] if sanction and not blocked else []
    result = _result(sanction, risk, blocked)
    gaps = [item.reason for item in missing]
    if source.answer.missing_internal_rule:
        gaps.append("Chưa có đoạn nội quy áp dụng.")
    report = _clean_minutes_text(source.answer.message or source.answer.rationale or "")
    case_meta = _case_description_meta(source.description)
    narrative = _incident_narrative(source, facts, report)
    sections = Sections(
        case_information=CaseInformation(
            case_code=source.case_code,
            incident_date=source.incident_date,
            violation_type=source.family,
            description=source.description or "",
            case_status=source.case_status,
        ),
        employee_information=EmployeeInformation(
            employee_code=source.employee_code,
            employee_name=source.employee_name,
            department=case_meta.get("department"),
            position=case_meta.get("position"),
            contract_type=_fact_value(facts, "contract_type"),
        ),
        incident_summary=IncidentSummary(
            narrative=narrative,
            hr_description=source.description or "",
            employee_statement=_fact_value(facts, "employee_statement") or "",
        ),
        confirmed_facts=facts,
        evidence_reviewed=cards,
        assessment=AssessmentSection(
            narrative=_clean_minutes_text(source.answer.rationale or report or narrative),
            applied_basis=[card.citation_label for card in cards if card.layer in {"legal_basis", "internal_rule"}],
            matches=[item.label for item in facts if item.status == "CONFIRMED"],
            gaps=gaps,
        ),
        assessment_result=result,
        handling_proposal=HandlingProposal(
            proposed_actions=proposed,
            confidence="MEDIUM" if proposed and risk in {"LOW", "MEDIUM"} else "LOW",
            requires_legal_review=not proposed or risk in {"HIGH", "CRITICAL"},
            rationale=_handling_summary(result, proposed, gaps),
        ),
        risk_and_gaps=RiskAndGaps(
            risk_level=risk,
            evidence_gaps=gaps,
            missing_information=missing,
            legal_review_required=True,
        ),
        next_steps=_steps(blocked, bool(proposed)),
        citations=cards,
    )
    sources = {
        "case_information.description": "AI",
        "employee_information.employee_name": "AI",
        "incident_summary.narrative": "AI",
        "handling_proposal.rationale": "AI",
    }
    return sections, sources


def _incident_narrative(source: ComposeInput, facts: list[ConfirmedFact], fallback: str) -> str:
    """Keep minutes narrative factual and readable, not a raw assessment report."""
    case_meta = _case_description_meta(source.description)
    items: list[str] = []
    if case_meta.get("violation"):
        items.append(case_meta["violation"])
    if case_meta.get("body"):
        items.append(case_meta["body"])
    if source.incident_date:
        items.append(f"Ngày xảy ra: {source.incident_date.isoformat()}")
    for fact in facts:
        if fact.fact_key in _INCIDENT_FACT_KEYS and fact.value and fact.status in {"CONFIRMED", "UNCERTAIN", "HR_EDITED"}:
            items.append(f"{fact.label}: {fact.value}")
    if not items and fallback:
        items.append(fallback)
    clean_items = [_clean_minutes_text(item).strip(" -.;") for item in items]
    return "\n".join(f"- {item}." for item in clean_items if item and not _looks_like_assessment_report(item))


def _case_description_meta(description: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    body: list[str] = []
    for line in (description or "").splitlines():
        text = line.strip()
        if not text:
            continue
        key, sep, value = text.partition(":")
        normalized = key.strip().casefold()
        clean_value = value.strip()
        if sep and normalized == "phòng ban":
            meta["department"] = clean_value
        elif sep and normalized in {"chức danh", "chức vụ", "vị trí"}:
            meta["position"] = clean_value
        elif sep and normalized == "vi phạm":
            meta["violation"] = clean_value
        else:
            body.append(text)
    if body:
        meta["body"] = " ".join(body)
    return meta


def _clean_minutes_text(value: str) -> str:
    text = _CHUNK_ID_RE.sub("", value or "")
    text = _MARKDOWN_RE.sub("", text)
    text = _ROMAN_HEADING_RE.sub("", text)
    text = re.sub(r"\b[IVXLCDM]{1,6}\.\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _handling_summary(result: AssessmentResult, proposed: list[ProposedAction], gaps: list[str]) -> str:
    if proposed:
        return f"{result.summary} Mức đề xuất để HR xem xét: {', '.join(item.label for item in proposed)}."
    if gaps:
        return f"{result.summary} Cần bổ sung: {'; '.join(gaps[:3])}."
    return result.summary


def _looks_like_assessment_report(value: str) -> bool:
    upper = value.upper()
    markers = ("BIÊN BẢN ĐÁNH GIÁ", "BIEN BAN ĐANH GIA", "KẾT QUẢ ĐÁNH GIÁ", "CĂN CỨ ĐÁNH GIÁ", "PHÂN TÍCH ĐIỀU KIỆN")
    return any(marker in upper for marker in markers) or "CHUNK_ID" in upper or "CHUNK ID" in upper


def known_chunk_ids(sections: Sections) -> set[str]:
    """Chunk ids copied onto the evidence list. A citation outside this list is forged."""
    return {str(item.chunk_id) for item in sections.evidence_reviewed if item.chunk_id is not None}


def _fact(item: FactInput) -> ConfirmedFact:
    if item.confirmed and item.value:
        status = "CONFIRMED"
    elif item.required:
        status = "MISSING"
    else:
        status = "UNCERTAIN"
    return ConfirmedFact(
        fact_key=item.key,
        label=item.label,
        value=item.value,
        status=status,
        blocking=item.required and status == "MISSING",
        source="CONFIRMED" if status == "CONFIRMED" else "AI",
    )


def _fact_value(facts: list[ConfirmedFact], key: str) -> str | None:
    for item in facts:
        if item.fact_key == key and item.value:
            return item.value
    return None


def _cards(answer: AnswerView) -> list[EvidenceCard]:
    rows: list[tuple[str, CitationView]] = []
    rows.extend(("legal_basis", item) for item in answer.legal_basis)
    rows.extend(("internal_rule", item) for item in answer.internal_rule)
    rows.extend(("precedent", item) for item in answer.precedent)
    rows.extend(("inspection_risk", item) for item in answer.inspection_risk)
    cards = []
    for index, (layer, item) in enumerate(rows, start=1):
        label = item.policy_name or item.policy_code or "Văn bản đã truy xuất"
        if item.article:
            label = f"{label} — Điều {item.article}"
        cards.append(
            EvidenceCard(
                evidence_id=f"EV-{index:03d}",
                document_id=None,
                chunk_id=item.chunk_id,
                policy_type=item.policy_type,
                title=item.policy_name or item.policy_code or "Văn bản đã truy xuất",
                citation_label=label,
                quote=item.quote,
                article=item.article,
                clause=item.clause,
                point=item.point,
                layer=layer,
            )
        )
    return cards


def _result(sanction: str | None, risk: str | None, blocked: bool) -> AssessmentResult:
    if blocked or sanction is None:
        return AssessmentResult(
            status="INSUFFICIENT_EVIDENCE",
            summary="Chưa đủ căn cứ để đề xuất một mức. Biên bản ghi phần đã có và phần còn thiếu.",
        )
    if risk in {"HIGH", "CRITICAL"}:
        return AssessmentResult(
            status="NEED_LEGAL_REVIEW",
            summary="Đã có mức tham khảo nhưng rủi ro căn cứ cao. HR xem biên bản trước khi xác nhận phiếu.",
        )
    return AssessmentResult(
        status="SUPPORTED",
        summary="Tình tiết bắt buộc đã có và mức tham khảo nằm trong văn bản đã truy xuất. HR vẫn phải xác nhận.",
    )


def _steps(blocked: bool, proposed: bool) -> list[NextStep]:
    rows = []
    order = 1
    if blocked:
        rows.append(NextStep(order=order, text="HR bổ sung tình tiết còn thiếu trong hội thoại."))
        order += 1
    rows.append(NextStep(order=order, text="HR xem và xác nhận biên bản."))
    order += 1
    if proposed and not blocked:
        rows.append(NextStep(order=order, text="HR xác nhận phiếu mà sub-agent soạn, rồi gửi pháp chế."))
        order += 1
    rows.append(NextStep(order=order, text="Pháp chế duyệt hoặc yêu cầu xử lý lại."))
    order += 1
    rows.append(NextStep(order=order, text="Quản lý duyệt lần cuối."))
    return rows
