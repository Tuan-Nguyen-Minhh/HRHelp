"""Generic reasoning contract and observable support scores, independent of case families.

No conduct-to-sanction table lives here. The model reads the retrieved instruments;
Python verifies references/data bindings and measures the resulting evidence support.
"""

from collections import Counter, defaultdict
from hashlib import sha256
from uuid import UUID

from src.features.answer.model.assessment import (
    Assessment,
    ConfidenceAssessment,
    IssuanceAssessment,
    IssuanceCheck,
    SourceSupport,
    SupportDimension,
)

RUBRIC_VERSION = "hr-reasoning-v1"

REASONING_RUBRIC = """
RUBRIC SUY LUẬN CHUNG hr-reasoning-v1 (áp dụng cho mọi hành vi, không có bảng ánh xạ case → mức):
1. Phân biệt tình tiết được HR xác nhận với cáo buộc và điều cần xác minh. Không tự bổ sung tình tiết.
2. Đọc nguồn cho đúng hành vi/đối tượng/thời điểm. Phân biệt nghĩa vụ, phân loại mức độ, điều khoản cho phép hình thức,
   điều kiện nội dung và yêu cầu ban hành. Danh mục hình thức chung chưa chứng minh hành vi thuộc hình thức đó.
3. Tự xây applicable_rules từ nguồn của lượt này, trích ngắn đủ điều kiện/ngoại lệ; purpose SANCTION/CONTEXT/PROCEDURE.
   selected=true chỉ cho nhánh đang dùng để chứng minh đề xuất; các nhánh thay thế đã loại phải selected=false.
   Không bỏ sót điều kiện bất lợi để nâng độ chắc chắn. fact/fact_value phải trùng dữ liệu đã xác nhận.
   scope SUBSTANTIVE cho điều kiện áp dụng hình thức; ISSUANCE cho việc cần hoàn thành trước ban hành.
   Các điều kiện không có alternative_group là AND bắt buộc. Mỗi alternative_group khác rỗng là một nhánh AND;
   chỉ cần một nhánh đáp ứng (OR giữa các nhóm). Không biến các trường hợp thay thế trong điều luật thành AND.
4. Chỉ chọn mức nguồn cho phép, giải thích ngắn quan hệ hành vi → điều kiện → hình thức. Không suy mức từ cảm tính,
   điểm nghiêm trọng, tiền lệ hoặc độ giống văn bản. Khi nhiều mức: giải thích cơ sở lựa chọn nếu nguồn cho phép
   cân nhắc; phải lựa chọn một mức phù hợp nhất và giải thích cơ sở lựa chọn, không chỉ liệt kê nhiều mức rồi bỏ trống
   đề xuất. Không tự chọn nặng nhất/nhẹ nhất. Nếu nguồn bác bỏ việc áp dụng thì kết luận chưa áp dụng kỷ luật.
5. rubric_reasoning.severity là mô tả tác động trên thang 1–5: 1 hạn chế/có thể khắc phục, 2 tác động thấp,
   3 tác động đáng kể, 4 tác động lớn, 5 tác động đặc biệt lớn. Đây là neo mô tả do sản phẩm đặt, không phải ngưỡng luật.
   Nêu reason, fact_keys và evidence chứng minh; chưa đủ dữ liệu thì score=null. Không lấy mức hình thức để suy ngược
   điểm nghiêm trọng, không suy ra lỗi/cố ý chỉ từ hậu quả. Không dùng đặc điểm cá nhân được bảo vệ để tăng mức.
6. rubric_reasoning.issuance_checks đánh giá riêng 5 category: TIME_LIMIT, PROTECTION, PROCEDURE, AUTHORITY,
   SOURCE_VALIDITY. requirement nêu việc cần kiểm tra, fact_values sao chép chính xác dữ liệu đối chiếu, evidence
   là quy định yêu cầu kiểm tra; result SATISFIED/NOT_SATISFIED/UNKNOWN/CONFLICTED. SATISFIED nghĩa là điều kiện
   cho phép tiến hành đã được chứng minh; ví dụ bảo vệ chưa được xác nhận không được ghi SATISFIED.
   effect PROCEDURE nếu còn việc phải hoàn tất, TEMPORARY_BLOCK nếu chưa được xử lý ở thời điểm này,
   LEGAL_BLOCK nếu có căn cứ ngăn áp dụng. next_action cụ thể, chỉ đúng thông tin/tài liệu cần thêm, không hỏi lại fact đã có.
   Thiếu nguồn/thời điểm dự kiến ban hành thì UNKNOWN và yêu cầu xác minh; không lấy incident_date thay ngày ban hành.
   Biên bản AI không chứng minh đã họp, minutes_made không tự chứng minh hoàn tất toàn bộ trình tự.
7. SUPPORTED phản ánh đề xuất về nội dung; chưa thực hiện thủ tục không tự làm mất đề xuất đã đủ căn cứ.
   Chỉ thiếu điều kiện SUBSTANTIVE mới vào missing_facts/evidence_gaps. Phần ban hành ghi issuance_checks.
   Nếu có căn cứ cấm áp dụng về nội dung, không gọi mức đó là đề xuất hợp lệ; chuyển NEED_LEGAL_REVIEW.
8. Không tự chấm xác suất đúng hoặc confidence phần trăm. Python tính EVIDENCE_SUPPORT_INDEX từ kiểm chứng;
   điểm này không phải xác suất pháp lý, điểm rerank cũng không phải độ tin cậy của kết luận.
9. Có dữ liệu truy xuất thì luôn đánh giá và ra quyết định xử lý. Ghi recommended_sanction là mức phù hợp nhất
   mà nguồn hỗ trợ; các điều kiện chưa rõ, thiếu nguồn đồng hành hoặc thủ tục được ghi riêng để kiểm tra trước áp dụng,
   không dùng chúng để bỏ trống mức đề xuất. Chỉ khi truy xuất không có dữ liệu mới trả lời chưa đủ căn cứ để đưa ra mức.
   Nếu tài liệu chỉ là tiền lệ/xử phạt hành chính, không liên quan hoặc có căn cứ cấm, quyết định chưa áp dụng kỷ luật
   và nêu việc cần làm; không bịa hình thức xử lý ngoài nguồn. Không tự ban hành quyết định.
Chỉ xuất kết luận ngắn, bảng điều kiện và căn cứ đủ kiểm tra; không xuất chuỗi suy nghĩ dài.
"""

ISSUANCE_CATEGORIES = {
    "TIME_LIMIT": "Xác minh thời hiệu tại ngày dự kiến ban hành và các mốc liên quan.",
    "PROTECTION": "Xác minh điều kiện cấm hoặc tạm hoãn xử lý tại thời điểm xem xét.",
    "PROCEDURE": "Đối chiếu hồ sơ thực hiện trình tự; bản nháp AI không chứng minh đã hoàn tất thủ tục.",
    "AUTHORITY": "Xác minh người có thẩm quyền và phê duyệt của con người.",
    "SOURCE_VALIDITY": "Xác minh phạm vi, phiên bản và hiệu lực pháp lý của các căn cứ áp dụng.",
}

ISSUANCE_LABELS = {
    "NEEDS_VERIFICATION": "Cần xác minh thêm",
    "NEEDS_PROCEDURE": "Cần hoàn thiện thủ tục",
    "TEMPORARILY_BLOCKED": "Đang có điều kiện tạm hoãn xử lý",
    "LEGALLY_BLOCKED": "Có điều kiện pháp lý ngăn áp dụng",
    "READY_FOR_HUMAN_REVIEW": "Có thể chuyển người có thẩm quyền xem xét",
}


def condition_result(conditions) -> str:
    """AND of mandatory predicates and OR of alternative AND branches (four states)."""
    if not conditions:
        return "UNKNOWN"

    def conjunction(results):
        if "CONFLICTED" in results:
            return "CONFLICTED"
        if "NOT_SATISFIED" in results:
            return "NOT_SATISFIED"
        return "SATISFIED" if results and all(item == "SATISFIED" for item in results) else "UNKNOWN"

    mandatory, groups = [], defaultdict(list)
    for condition in conditions:
        if condition.alternative_group:
            groups[condition.alternative_group].append(condition.result)
        else:
            mandatory.append(condition.result)
    if groups:
        branches = [conjunction(results) for results in groups.values()]
        alternative = (
            "SATISFIED"
            if "SATISFIED" in branches
            else "CONFLICTED"
            if "CONFLICTED" in branches
            else "UNKNOWN"
            if "UNKNOWN" in branches
            else "NOT_SATISFIED"
        )
        mandatory.append(alternative)
    return conjunction(mandatory)


def evaluate_support(
    assessment: Assessment, *, valid_citations: int, total_citations: int, passages, raw_refs=(), valid_refs=()
) -> ConfidenceAssessment:
    """Conservative bottleneck index; a high score never unlocks a sanction."""
    selected = [
        rule
        for rule in assessment.applicable_rules
        if rule.selected
        and rule.purpose == "SANCTION"
        and rule.supports_sanction == assessment.sanction_assessment.recommended_sanction
    ]
    roles = {rule.document_type for rule in selected if rule.evidence}
    source_score = 100 if "INTERNAL_RULE" in roles and roles & {"LAW", "DECREE"} else 40 if roles else 0
    citation_score = round(100 * valid_citations / total_citations) if total_citations else 0
    results = [condition_result([item for item in rule.conditions if item.scope == "SUBSTANTIVE"]) for rule in selected]
    condition_score = round(100 * results.count("SATISFIED") / len(results)) if results else 0
    consistency_score = (
        0
        if assessment.conflicts or "CONFLICTED" in results
        else 60
        if assessment.risk_assessment.level == "HIGH"
        else 100
    )
    used_ids = {ref.chunk_id for rule in selected for ref in rule.evidence}
    used = [item for item in passages if str(item.chunk_id) in used_ids]
    retrieval_score = (
        100 if used and all(item.retrieval_status == "OK" and not item.evidence_gaps for item in used) else 60
    )
    if any(item.retrieval_status in {"DEGRADED", "INCOMPLETE"} or item.evidence_gaps for item in used):
        retrieval_score = 20
    dimensions = [
        SupportDimension(
            key="source_roles",
            score=source_score,
            explanation="Có nguồn nội quy và luật/hướng dẫn cho đề xuất; chưa phải xác minh độc lập hiệu lực pháp lý.",
        ),
        SupportDimension(
            key="citation_integrity",
            score=citation_score,
            explanation="Tỷ lệ trích dẫn đề xuất/nhánh đã chọn khớp đúng nội dung hoặc tiêu đề cùng chunk.",
        ),
        SupportDimension(
            key="condition_support",
            score=condition_score,
            explanation="Tỷ lệ nhánh đã chọn đủ điều kiện nội dung và liên kết tình tiết được kiểm tra.",
        ),
        SupportDimension(
            key="consistency",
            score=consistency_score,
            explanation="Không phát hiện xung đột trong kết quả đối chiếu; không bảo đảm không còn xung đột ngoài bộ nguồn.",
        ),
        SupportDimension(
            key="retrieval_health",
            score=retrieval_score,
            explanation="Trạng thái đầy đủ của gói truy xuất; không đo tính đúng đắn pháp lý hay xác suất đúng.",
        ),
    ]
    score = min(item.score for item in dimensions)
    if not assessment.downstream_handoff.can_recommend:
        score = min(score, 49)
    if assessment.operational_status != "OK":
        score = 0

    def ref_key(ref):
        try:
            return str(UUID(ref.chunk_id))
        except ValueError:
            return ref.chunk_id

    raw_counts, valid_counts = Counter(map(ref_key, raw_refs)), Counter(map(ref_key, valid_refs))
    return ConfidenceAssessment(
        rubric_version=RUBRIC_VERSION,
        score=score,
        label="HIGH" if score >= 85 else "MEDIUM" if score >= 60 else "LOW",
        dimensions=dimensions,
        sources=[
            SourceSupport(
                chunk_id=str(item.chunk_id),
                policy_version_id=str(item.policy_version_id),
                document_role=item.policy_type or "UNKNOWN",
                content_sha256=sha256(item.content.encode("utf-8")).hexdigest(),
                heading_sha256=sha256(item.section_title.encode("utf-8")).hexdigest(),
                citation_integrity_score=round(
                    100 * valid_counts[str(item.chunk_id)] / max(1, raw_counts[str(item.chunk_id)])
                ),
                retrieval_status=item.retrieval_status,
            )
            for item in passages
            if raw_counts[str(item.chunk_id)]
        ],
        limitations=[
            "Điểm hỗ trợ của căn cứ, không phải phần trăm xác suất kết luận đúng; chưa được hiệu chuẩn bằng hồ sơ chuyên gia.",
            "Đối chiếu ngữ nghĩa do LLM thực hiện; HR cần kiểm tra chứng cứ gốc và hiệu lực nguồn trước khi ban hành.",
        ],
    )


def evaluate_issuance(assessment: Assessment) -> IssuanceAssessment:
    checks = list(assessment.rubric_reasoning.issuance_checks)
    present = {item.category for item in checks}
    for category, action in ISSUANCE_CATEGORIES.items():
        if category not in present:
            checks.append(IssuanceCheck(category=category, requirement=action, next_action=action))
    if any(item.result == "NOT_SATISFIED" and item.effect == "LEGAL_BLOCK" for item in checks):
        status = "LEGALLY_BLOCKED"
    elif any(item.result == "NOT_SATISFIED" and item.effect == "TEMPORARY_BLOCK" for item in checks):
        status = "TEMPORARILY_BLOCKED"
    elif any(item.result == "NOT_SATISFIED" for item in checks):
        status = "NEEDS_PROCEDURE"
    elif (
        not assessment.downstream_handoff.can_recommend
        or assessment.downstream_handoff.needs_legal_review
        or any(item.result != "SATISFIED" for item in checks)
    ):
        status = "NEEDS_VERIFICATION"
    else:
        status = "READY_FOR_HUMAN_REVIEW"
    actions = [item.next_action or item.requirement for item in checks if item.result != "SATISFIED"]
    if not assessment.downstream_handoff.can_recommend:
        actions.insert(0, "Hoàn tất xác minh căn cứ và điều kiện của mức xử lý đề xuất.")
    if assessment.downstream_handoff.needs_legal_review:
        actions.append("Người có chuyên môn cần rà soát các điểm rủi ro hoặc bất định trong đánh giá.")
    return IssuanceAssessment(status=status, checks=checks, next_actions=list(dict.fromkeys(actions)))
