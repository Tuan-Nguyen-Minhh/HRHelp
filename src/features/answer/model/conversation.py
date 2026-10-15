"""A short chat reply from the guarded assessment; the full report stays stored."""

from src.features.answer.model.assessment import Assessment
from src.features.answer.model.decide import SanctionDecision
from src.features.answer.model.layers import LayeredBasis
from src.features.answer.schema import SANCTION_LABELS, AnswerView
from src.features.clarify.model.catalog import fact_label


def assessment_reply(assessment: Assessment | None, decision: SanctionDecision, layered: LayeredBasis) -> str:
    if decision.sanction_type:
        text = (
            f"Với các tình tiết đã xác nhận, tôi đề xuất mức {sanction_label(decision.sanction_type)} cho vụ việc này."
        )
    elif assessment is not None and assessment.operational_status != "OK":
        text = "Tôi chưa hoàn tất việc tổng hợp căn cứ nên chưa thể đề xuất mức xử lý. Bạn hãy thử lại bước phân tích hồ sơ."
    elif assessment is not None and assessment.sanction_assessment.recommended_sanction:
        text = (
            f"Bản đánh giá đang xem xét hình thức {sanction_label(assessment.sanction_assessment.recommended_sanction)}. "
            "Tôi chưa thể chốt mức đề xuất vì còn điều kiện hoặc căn cứ cần kiểm tra."
        )
    else:
        text = "Tôi đã đối chiếu các thông tin của vụ việc, nhưng hiện chưa đủ căn cứ để đề xuất một mức xử lý cụ thể."
    parts = [text]
    if assessment is not None and assessment.operational_status == "OK":
        parts.append(short_explanation(assessment.sanction_assessment.reason))
        if assessment.confidence.label != "UNASSESSED":
            parts.append(confidence_sentence(assessment.confidence))
        if decision.sanction_type and assessment.risk_assessment.level == "HIGH" and assessment.risk_assessment.reasons:
            parts.append(
                "Các điểm cần rà soát thêm: " + short_explanation("; ".join(assessment.risk_assessment.reasons[:2]))
            )
        severity = assessment.rubric_reasoning.severity
        if severity.score is not None:
            parts.append(f"Mức độ nghiêm trọng tham khảo: {severity.score}/5. {short_explanation(severity.reason)}")
        if assessment.issuance.status == "TEMPORARILY_BLOCKED":
            parts.append("Hồ sơ đang có điều kiện tạm hoãn xử lý; chưa thể tiến hành ban hành tại thời điểm này.")
        elif assessment.issuance.status == "LEGALLY_BLOCKED":
            parts.append("Có điều kiện pháp lý ngăn áp dụng; cần rà soát lại trước khi lựa chọn hình thức xử lý.")
        index = {str(item.chunk_id): item for item in [*layered.legal_basis, *layered.internal_rule]}
        refs = [
            *assessment.sanction_assessment.evidence,
            *[
                ref
                for rule in assessment.applicable_rules
                if rule.selected and rule.purpose == "SANCTION"
                for ref in rule.evidence
            ],
        ]
        grouped = {}
        for ref in refs:
            item = index.get(ref.chunk_id)
            content = (item.section_title if ref.source == "HEADING" else item.content) if item else ""
            if item is None or not ref.quote or ref.quote not in content:
                continue
            grouped.setdefault(ref.chunk_id, [])
            if ref.quote not in grouped[ref.chunk_id]:
                grouped[ref.chunk_id].append(ref.quote)
        sources = []
        for chunk_id, quotes in list(grouped.items())[:3]:
            item = index[chunk_id]
            label = source_label(item.policy_name, item.article, item.clause, item.point)
            excerpts = "; ".join(f"“{short_quote(quote)}”" for quote in quotes[:2])
            sources.append(f"- {label}: {excerpts}")
        if sources:
            parts.append("Các căn cứ tôi đã đối chiếu:\n" + "\n".join(sources))
        if assessment.case_summary.missing_facts:
            questions = [
                gap.question_for_user
                for gap in assessment.evidence_gaps
                if gap.fact in assessment.case_summary.missing_facts
            ]
            covered = {gap.fact for gap in assessment.evidence_gaps}
            for key in assessment.case_summary.missing_facts:
                if key in covered:
                    continue
                label = fact_label(key)
                if label != key:
                    questions.append(label)
            if questions:
                parts.append(
                    "Để tiếp tục xác định mức phù hợp, bạn giúp tôi làm rõ:\n"
                    + "\n".join(f"- {question}" for question in dict.fromkeys(questions))
                )
            else:
                parts.append("Tôi cần làm rõ thêm tình tiết nêu trong biên bản trước khi xác định mức xử lý.")
        elif decision.sanction_type is None:
            parts.append("Phần căn cứ và điều kiện áp dụng còn cần kiểm tra trước khi đưa ra đề xuất.")
        if assessment.issuance.next_actions:
            parts.append(
                "Trước khi ban hành, cần hoàn thành hoặc xác minh:\n"
                + "\n".join(f"- {action}" for action in assessment.issuance.next_actions[:3])
            )
        elif assessment.issuance.status == "READY_FOR_HUMAN_REVIEW":
            parts.append("Hồ sơ có thể chuyển người có thẩm quyền xem xét và phê duyệt.")
    return "\n\n".join(parts)


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
