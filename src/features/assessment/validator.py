"""Check a composed form. Citations outside the stored evidence are blocking errors."""

from src.features.assessment.agent import known_chunk_ids
from src.features.assessment.schemas import Sections, ValidationState

_COMPANY = frozenset({"WARNING", "REPRIMAND", "WAGE_POSTPONEMENT", "DEMOTION", "DISMISSAL"})


def validate_sections(sections: Sections, allowed_chunk_ids: set[str] | None = None) -> ValidationState:
    """Required facts and citation ids block confirm. Other gaps stay warnings."""
    blocking: list[str] = []
    warnings: list[str] = []
    for item in sections.confirmed_facts:
        if item.blocking or (item.status == "MISSING" and item.blocking):
            blocking.append(f"Thiếu {item.label}.")
        elif item.status == "MISSING":
            warnings.append(f"Chưa có {item.label}.")
    allowed = known_chunk_ids(sections) if allowed_chunk_ids is None else allowed_chunk_ids
    cards = sections.citations if allowed_chunk_ids is None else [*sections.citations, *sections.evidence_reviewed]
    for card in cards:
        if card.chunk_id is not None and str(card.chunk_id) not in allowed:
            blocking.append(f"Căn cứ {card.citation_label} không nằm trong văn bản đã truy xuất.")
    for action in sections.handling_proposal.proposed_actions:
        if action.code not in _COMPANY:
            blocking.append("Đề xuất chứa mức không phải kỷ luật công ty.")
    if sections.handling_proposal.requires_legal_review and not sections.handling_proposal.proposed_actions:
        warnings.append("Chưa có mức tham khảo. Phiếu pháp chế chưa được mở.")
    for gap in sections.risk_and_gaps.evidence_gaps:
        if gap not in blocking and gap not in warnings:
            warnings.append(gap)
    unique_blocking = list(dict.fromkeys(blocking))
    return ValidationState(is_valid=not unique_blocking, blocking_errors=unique_blocking, warnings=warnings)
