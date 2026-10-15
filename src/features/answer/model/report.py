"""Render the guarded assessment; no second model call and no invented procedure."""

from src.agents.handoff import CaseHandoff
from src.features.answer.model.assessment import Assessment
from src.features.answer.model.conversation import confidence_sentence
from src.features.answer.model.rubric import ISSUANCE_LABELS
from src.features.answer.schema import SANCTION_LABELS
from src.features.clarify.model.catalog import fact_label


def render_report(message: CaseHandoff, assessment: Assessment) -> str:
    def section(title, lines):
        return title + "\n" + ("\n".join(lines) if lines else "Chưa xác định.")

    sanction = assessment.sanction_assessment
    level = SANCTION_LABELS.get(sanction.recommended_sanction, "Chưa xác định")
    all_refs = [
        *sanction.evidence,
        *[ref for rule in assessment.applicable_rules for ref in rule.evidence],
        *[ref for step in assessment.procedure_assessment.steps for ref in step.evidence],
        *[ref for check in assessment.issuance.checks for ref in check.evidence],
    ]
    refs = list(dict.fromkeys((ref.chunk_id, ref.quote, ref.source) for ref in all_refs))
    result_labels = {
        "SATISFIED": "Đáp ứng",
        "NOT_SATISFIED": "Không đáp ứng",
        "UNKNOWN": "Chưa xác định",
        "CONFLICTED": "Mâu thuẫn",
    }
    conditions = [
        f"- {condition.required}: {result_labels[condition.result]}. Tình tiết thực tế: {condition.fact_value or 'chưa xác nhận'}."
        for rule in assessment.applicable_rules
        if rule.selected
        for condition in rule.conditions
    ]
    missing = list(
        dict.fromkeys(
            [
                *assessment.case_summary.missing_facts,
                *[gap.question_for_user for gap in assessment.evidence_gaps],
                *[
                    condition.fact
                    for rule in assessment.applicable_rules
                    if rule.selected
                    for condition in rule.conditions
                    if condition.scope == "SUBSTANTIVE"
                    and condition.result == "UNKNOWN"
                    and not assessment.case_summary.facts.get(condition.fact)
                ],
            ]
        )
    )
    index = {str(item.chunk_id): item for item in message.passages}
    sources = []
    for chunk_id, quote, source in refs:
        item = index.get(chunk_id)
        if item:
            sources.append(
                f'- {item.policy_name}, Điều {item.article or "?"}, khoản {item.clause or "?"} [{chunk_id}, {source}, phiên bản {item.policy_version_id}]: "{quote}"'
            )
    return "\n\n".join(
        [
            "BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC",
            section(
                "I. THÔNG TIN VỤ VIỆC",
                [
                    f"Nhân viên: {message.employee_name or 'chưa có'}.",
                    f"Ngày xảy ra: {message.incident_date.strftime('%d/%m/%Y')}. Nhóm: {message.family}.",
                ],
            ),
            section(
                "II. TÌNH TIẾT ĐÃ XÁC NHẬN",
                message.fact_lines or [f"- {fact_label(key)}: {value}" for key, value in message.facts.items()],
            ),
            section(
                "III. TÌNH TIẾT CHƯA XÁC ĐỊNH",
                missing or ["Không có tình tiết còn thiếu trong các điều kiện đã đối chiếu."],
            ),
            section(
                "IV. KẾT QUẢ ĐÁNH GIÁ",
                [
                    f"Trạng thái: {sanction.status}. Mức đề xuất: {level}.",
                    sanction.reason,
                    confidence_sentence(assessment.confidence),
                    f"Mức độ nghiêm trọng tham khảo: {assessment.rubric_reasoning.severity.score or 'chưa xác định'}/5. {assessment.rubric_reasoning.severity.reason}",
                ],
            ),
            section("V. CĂN CỨ ĐÁNH GIÁ", sources),
            section("VI. PHÂN TÍCH ĐIỀU KIỆN", conditions),
            section(
                "VII. QUY TRÌNH XỬ LÝ",
                [
                    f"Trạng thái ban hành: {ISSUANCE_LABELS[assessment.issuance.status]}.",
                    *[f"- {check.requirement}: {result_labels[check.result]}." for check in assessment.issuance.checks],
                    *[f"Cần làm: {action}" for action in assessment.issuance.next_actions],
                ],
            ),
            section(
                "VIII. RỦI RO CĂN CỨ",
                [
                    assessment.risk_assessment.level,
                    *assessment.risk_assessment.reasons,
                    *[
                        f"- {item.key}: {item.score}/100. {item.explanation}"
                        for item in assessment.confidence.dimensions
                    ],
                    *[
                        f"- Nguồn {item.chunk_id}, phiên bản {item.policy_version_id}: khớp trích dẫn {item.citation_integrity_score}/100; SHA256 nội dung {item.content_sha256}; SHA256 tiêu đề {item.heading_sha256}. {item.note}"
                        for item in assessment.confidence.sources
                    ],
                    *assessment.confidence.limitations,
                ],
            ),
            section("IX. CÁC ĐIỂM CẦN HR XÁC NHẬN", missing),
            section(
                "X. KẾT LUẬN ĐỂ HR XEM XÉT",
                [
                    sanction.reason,
                    "Mức có thể chuyển bước xem xét."
                    if assessment.downstream_handoff.can_recommend
                    else "Mức chưa được khóa. Cần bổ sung hoặc kiểm tra căn cứ trước khi tiếp tục.",
                ],
            ),
            section(
                "XI. QUYẾT ĐỊNH CỦA HR",
                [
                    "HR đồng ý với đánh giá; HR yêu cầu bổ sung thông tin; "
                    "HR gửi hồ sơ cho pháp chế; HR không sử dụng kết quả đánh giá này.",
                    "Biên bản này không tự ban hành quyết định kỷ luật.",
                ],
            ),
        ]
    )
