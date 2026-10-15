"""A short chat reply from the guarded assessment; the full report stays stored."""

from src.features.answer.model.assessment import Assessment
from src.features.answer.model.decide import SanctionDecision
from src.features.answer.model.layers import LayeredBasis
from src.features.answer.schema import SANCTION_LABELS, AnswerView
from src.features.clarify.model.catalog import fact_label

# Guard annotations remain intact in the stored assessment and report. Chat places
# their meaning next to the verification work, rather than inside the conclusion.
_GUARD_NOTES = {
    "Chưa chứng minh đầy đủ điều kiện bằng tình tiết đã xác nhận và trích dẫn.": "đối chiếu thêm các điều kiện áp dụng với tình tiết và trích dẫn gốc",
    "Tình tiết đã có nhưng việc áp dụng điều kiện chưa được chứng minh bằng trích dẫn phù hợp.": "kiểm tra trích dẫn chứng minh điều kiện áp dụng đối với các tình tiết đã có",
    "Đề xuất mâu thuẫn với điều kiện hoặc xung đột căn cứ; cần kiểm tra lại.": "làm rõ điều kiện chưa đáp ứng hoặc điểm mâu thuẫn giữa các căn cứ",
}
_GENERIC_VERIFICATION = "Hoàn tất xác minh căn cứ và điều kiện của mức xử lý đề xuất."


def assessment_reply(assessment: Assessment | None, decision: SanctionDecision, layered: LayeredBasis) -> str:
    if not (layered.legal_basis or layered.internal_rule or layered.precedent or layered.inspection_risk):
        return "Chưa có đủ căn cứ để đưa ra mức xử lý vì không truy xuất được dữ liệu cho vụ việc."
    if assessment is not None and assessment.operational_status != "OK":
        return "Tôi chưa hoàn tất việc tổng hợp căn cứ nên chưa thể đề xuất mức xử lý. Bạn hãy thử lại bước phân tích hồ sơ."
    level = decision.sanction_type or (assessment.sanction_assessment.recommended_sanction if assessment else None)
    opening = (
        f"Với các tình tiết đã xác nhận, tôi đề xuất mức {sanction_label(level)} cho vụ việc này."
        if level
        else "Tôi đề xuất chưa áp dụng kỷ luật theo các tài liệu đã đối chiếu."
    )
    if assessment is None:
        return opening
    if assessment.confidence.label != "UNASSESSED":
        opening += " " + chat_confidence_sentence(
            assessment.confidence, verify=bool(level and assessment.confidence.label == "LOW")
        )
    parts = [opening]

    reason = assessment.sanction_assessment.reason
    verification = []
    for note, action in _GUARD_NOTES.items():
        if note in reason:
            reason = reason.replace(note, "")
            verification.append(action)
    reason = short_explanation(reason)
    if reason:
        if level and not assessment.downstream_handoff.can_recommend:
            reason = "Đề xuất này dựa trên nhận định ban đầu rằng " + lower_start(reason)
        severity = assessment.rubric_reasoning.severity
        if severity.score is not None:
            reason += f" Mức độ nghiêm trọng được đánh giá tham khảo là {severity.score}/5 theo các tình tiết hiện có."
        parts.append(reason)

    risks = risk_notes(assessment.risk_assessment.reasons) if assessment.risk_assessment.level == "HIGH" else []
    caveats = []
    if verification:
        notes = list(dict.fromkeys(clean_sentence(note) for note in verification if clean_sentence(note)))
        caveats.append("Tuy nhiên, cần " + "; ".join(lower_start(note) for note in notes[:3]) + ".")
    if risks:
        caveats.append("Hiện tại, " + lower_start(risks[0]) + ".")
        caveats.extend(note[:1].upper() + note[1:] + "." for note in risks[1:2])
    if caveats:
        parts.append(" ".join(caveats))
    if assessment.issuance.status == "TEMPORARILY_BLOCKED":
        parts.append("Hồ sơ đang có điều kiện tạm hoãn xử lý; chưa thể tiến hành ban hành tại thời điểm này.")
    elif assessment.issuance.status == "LEGALLY_BLOCKED":
        parts.append("Có điều kiện pháp lý ngăn áp dụng; cần rà soát lại trước khi lựa chọn hình thức xử lý.")

    index = {str(item.chunk_id): item for item in [*layered.legal_basis, *layered.internal_rule]}
    selected = [rule for rule in assessment.applicable_rules if rule.selected and rule.purpose == "SANCTION"]
    # Conditions carry the useful application clause; an introductory sentence
    # or repeated heading must not crowd it out of the short source excerpts.
    refs = [
        *[
            ref
            for rule in selected
            for condition in rule.conditions
            if condition.scope == "SUBSTANTIVE"
            for ref in condition.evidence
        ],
        *assessment.sanction_assessment.evidence,
        *[ref for rule in selected for ref in rule.evidence],
    ]
    grouped = {}
    for ref in refs:
        item = index.get(ref.chunk_id)
        content = (item.section_title if ref.source == "HEADING" else item.content) if item else ""
        if item is None or not ref.quote or ref.quote not in content:
            continue
        grouped.setdefault(ref.chunk_id, [])
        entry = (ref.source, ref.quote)
        if entry not in grouped[ref.chunk_id]:
            grouped[ref.chunk_id].append(entry)
    sources = []
    for chunk_id, entries in list(grouped.items())[:3]:
        item = index[chunk_id]
        label = source_label(item.policy_name, item.article, item.clause, item.point)
        headings = [quote for source, quote in entries if source == "HEADING"]
        bodies = [quote for source, quote in entries if source == "CONTENT"]
        quotes = list(dict.fromkeys([*headings[:1], *bodies]))[:2]
        excerpts = "; ".join(f"“{short_quote(quote)}”" for quote in quotes)
        sources.append(f"- {label}: {excerpts}")
    if sources:
        parts.append("Các căn cứ được dùng để đối chiếu đề xuất này:\n" + "\n".join(sources))

    if assessment.case_summary.missing_facts:
        questions = [
            gap.question_for_user
            for gap in assessment.evidence_gaps
            if gap.fact in assessment.case_summary.missing_facts
        ]
        covered = {gap.fact for gap in assessment.evidence_gaps}
        for key in assessment.case_summary.missing_facts:
            label = fact_label(key)
            if key not in covered and label != key:
                questions.append(label)
        if questions:
            parts.append(
                "Để hoàn thiện việc đối chiếu, bạn giúp tôi làm rõ:\n"
                + "\n".join(f"- {question}" for question in dict.fromkeys(questions))
            )
        else:
            parts.append("Cần làm rõ thêm tình tiết nêu trong biên bản để kiểm tra điều kiện áp dụng mức đề xuất.")
    actions = list(assessment.issuance.next_actions)
    if verification and len(actions) > 1:
        actions = [action for action in actions if action != _GENERIC_VERIFICATION]
    if actions:
        parts.append(
            "Trước khi ban hành quyết định, cần "
            + "; ".join(lower_start(clean_sentence(action)) for action in actions[:3])
            + "."
        )
    elif assessment.issuance.status == "READY_FOR_HUMAN_REVIEW":
        parts.append("Sau bước đối chiếu này, hồ sơ có thể chuyển người có thẩm quyền xem xét và phê duyệt.")
    return "\n\n".join(parts)


def clean_sentence(text: str) -> str:
    return " ".join(text.split()).rstrip(" .;")


def lower_start(text: str) -> str:
    # Preserve initials such as HR and API when joining a sentence.
    return text[:1].lower() + text[1:] if len(text) > 1 and text[1].islower() else text


def risk_notes(reasons: list[str]) -> list[str]:
    notes = []
    for reason in reasons:
        reason = clean_sentence(reason)
        if reason.casefold().startswith(("có đủ căn cứ", "đã có đủ căn cứ", "đủ căn cứ")):
            # Keep a qualification after a positive statement, if one exists.
            for connector in (" nhưng ", " tuy nhiên "):
                position = reason.casefold().find(connector)
                if position >= 0:
                    reason = reason[position + len(connector) :]
                    break
            else:
                continue
        if reason:
            notes.append(reason)
    return notes


def chat_confidence_sentence(confidence, *, verify: bool = False) -> str:
    labels = {"LOW": "thấp", "MEDIUM": "trung bình", "HIGH": "cao", "UNASSESSED": "chưa đánh giá"}
    text = f"Căn cứ hỗ trợ mức xử lý này được đánh giá {confidence.score}/100 ({labels[confidence.label]})"
    return text + (", nên cần kiểm chứng thêm trước khi áp dụng." if verify else ".")


def confidence_sentence(confidence) -> str:
    labels = {"LOW": "thấp", "MEDIUM": "trung bình", "HIGH": "cao", "UNASSESSED": "chưa đánh giá"}
    return (
        f"Điểm hỗ trợ của căn cứ: {confidence.score}/100 ({labels[confidence.label]}). "
        "Điểm này chưa phải xác suất kết luận đúng."
    )


def answer_reply(answer: AnswerView) -> str:
    """Use the saved summary; safely summarize older recommendations without their report body."""
    if answer.chat_message:
        return answer.chat_message
    parts = [
        f"Với các tình tiết đã xác nhận, tôi đề xuất mức {sanction_label(answer.sanction_type)} cho vụ việc này."
        if answer.sanction_type
        else "Tôi chưa thể đề xuất một mức xử lý cụ thể vì căn cứ hoặc điều kiện áp dụng chưa đầy đủ."
    ]
    if answer.confidence is not None and answer.confidence.label != "UNASSESSED":
        parts[0] += " " + chat_confidence_sentence(answer.confidence)
    sources = []
    seen = set()
    for ref in [*answer.internal_rule, *answer.legal_basis]:
        label = source_label(ref.policy_name, ref.article, ref.clause, ref.point)
        if label in seen or not ref.quote:
            continue
        seen.add(label)
        sources.append(f"- {label}: “{short_quote(ref.quote)}”")
        if len(sources) == 3:
            break
    if sources:
        parts.append("Các căn cứ đã đối chiếu:\n" + "\n".join(sources))
    return "\n\n".join(parts)


def sanction_label(code: str) -> str:
    return SANCTION_LABELS[code].split(" (", 1)[0]


def source_label(name: str | None, article: str | None, clause: str | None, point: str | None) -> str:
    return ", ".join(
        part
        for part in [
            name or "Văn bản đã đối chiếu",
            f"Điều {article}" if article else "",
            f"khoản {clause}" if clause else "",
            f"điểm {point}" if point else "",
        ]
        if part
    )


def short_quote(quote: str) -> str:
    cleaned = " ".join(quote.split())
    return cleaned if len(cleaned) <= 220 else cleaned[:220].rsplit(" ", 1)[0] + "…"


def short_explanation(reason: str) -> str:
    cleaned = " ".join(reason.split())
    return cleaned if len(cleaned) <= 450 else cleaned[:450].rsplit(" ", 1)[0] + "…"
