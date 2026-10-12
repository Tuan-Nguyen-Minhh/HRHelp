"""Extract source DOCX cases and build a draft RAGAS assessment dataset.

Run with the bundled document runtime. Does not call an LLM or change sources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

CASES = [
    {
        "id": "CA01", "file": "01_Bien_ban_nghi_khong_phep.docx",
        "name": "NGUYỄN VĂN AN", "employee_code": "EMP-005",
        "job": "Kỹ sư phần mềm", "department": "Kỹ thuật",
        "family": "UNAUTHORIZED_ABSENCE", "event_date": "2026-10-05",
        "event_end": "2026-10-09", "minutes_date": "2026-10-12",
        "facts": {"absence_days": "5 ngày làm việc trong 30 ngày (05–09/10/2026)", "notice_form": "không báo", "minutes_made": "true"},
        "unknown": ["contract_type", "explanation_requested", "justified_absence_reason"],
        "rules": [("NQCT", "4"), ("NQCT", "13"), ("BLLD_2019", "125")],
        "finding": "Đã có 5 ngày vắng mặt cụ thể trong một khoảng 30 ngày. Điều 13 nội quy và Điều 125 khoản 4 Bộ luật Lao động còn yêu cầu không có lý do chính đáng. Lời trình bày 'việc gia đình' chưa đủ để xác định lý do chính đáng có tồn tại hay không; cũng không được coi việc chưa thông báo là bằng chứng tự động loại trừ mọi lý do chính đáng.",
        "conditions": ["Số ngày và khoảng thời gian: SATISFIED theo các ngày 05–09/10/2026.", "Không có lý do chính đáng: UNKNOWN; cần giải trình và tài liệu xác minh."],
        "conclusion": "Chưa đề xuất sa thải một cách dứt khoát. Yêu cầu làm rõ lý do và tài liệu chứng minh; chỉ đánh giá lại hình thức xử lý sau khi xác nhận điều kiện còn thiếu.",
        "questions": ["Nhân viên thuộc loại hợp đồng nào?", "Đã gửi yêu cầu giải trình chính thức chưa?", "Việc gia đình cụ thể là gì, có thuộc lý do chính đáng và có tài liệu chứng minh không?"],
        "checks": ["Nhận diện 5 ngày trong 30 ngày", "Không suy diễn việc gia đình thành lý do hợp lệ hoặc không hợp lệ", "Không đề xuất sa thải vô điều kiện"],
    },
    {
        "id": "CA02", "file": "02_Bien_ban_di_muon.docx",
        "name": "TRẦN THỊ BÌNH", "employee_code": "EMP-012",
        "job": "Chuyên viên kinh doanh", "department": "Kinh doanh",
        "family": "LATE", "event_date": "2026-10-05", "event_end": "2026-10-12", "minutes_date": "2026-10-13",
        "facts": {"late_days": "4 lần trong tháng 10/2026", "minutes_made": "true"},
        "unknown": ["contract_type", "explanation_requested", "first_offense", "justified_lateness_reason"],
        "rules": [("NQCT", "3"), ("NQCT", "11"), ("BLLD_2019", "124")],
        "finding": "Ca sáng bắt đầu lúc 08:30 theo Điều 3 nội quy trong snapshot. Bốn lần đến lúc 08:50, 08:45, 09:00 và 08:55 tương ứng muộn 20, 15, 30 và 25 phút, tổng 90 phút. Cả bốn lần đạt ngưỡng từ 15 phút và số lần vượt quá 03 trong một tháng. Điều 11 yêu cầu phạm lỗi lần đầu và không có lý do chính đáng. Chưa có lịch sử vi phạm; lời trình bày về sắp xếp việc cá nhân cần được xác minh nếu dùng để kết luận về lý do chính đáng.",
        "conditions": ["Mỗi lần muộn từ 15 phút trở lên: SATISFIED.", "Quá 03 lần trong một tháng: SATISFIED (4 lần).", "Phạm lỗi lần đầu: UNKNOWN.", "Không có lý do chính đáng: UNKNOWN với thông tin hiện có."],
        "conclusion": "Điều 11 có quy định khiển trách bằng văn bản có thể áp dụng nếu xác nhận đủ các điều kiện. Hiện chưa chốt mức; cần xác minh lịch sử và lý do, đồng thời hoàn thiện thông tin hợp đồng và thủ tục. Không coi việc chưa ban hành quyết định là bằng chứng rằng không có hình thức nào có thể được đề xuất.",
        "questions": ["Loại hợp đồng là gì?", "Đã gửi yêu cầu giải trình chính thức chưa?", "Đây có phải lần đầu vi phạm không?", "Có lý do chính đáng hoặc sự chấp thuận nào cho các lần đến muộn không?"],
        "checks": ["Tính đúng 20 + 15 + 30 + 25 = 90 phút", "Dùng ngưỡng quá 3 lần của snapshot, không dùng ngưỡng 7 lần của Markdown cũ", "Không tự điền first_offense"],
    },
    {
        "id": "CA03", "file": "03_Bien_ban_cham_nop_bao_cao.docx",
        "name": "LÊ VĂN CƯỜNG", "employee_code": "EMP-021",
        "job": "Chuyên viên kế toán", "department": "Tài chính Kế toán",
        "family": "GENERAL", "event_date": "2026-10-09", "event_end": "2026-10-13", "minutes_date": "2026-10-14",
        "facts": {"violation_summary": "Nộp báo cáo đối soát tháng 9 sau hạn 17:00 ngày 09/10/2026, gửi lúc 10:00 ngày 13/10/2026; chưa đề nghị gia hạn trước hạn.", "minutes_made": "true"},
        "unknown": ["contract_type", "explanation_requested", "first_offense", "subjective_fault", "supporting_document_availability"],
        "rules": [("NQCT", "11"), ("BLLD_2019", "122"), ("BLLD_2019", "124")],
        "finding": "Thời điểm nộp muộn được mô tả cụ thể và có thư giao việc, nhắc hạn, gửi báo cáo. Điều 11 đề cập không hoàn thành nhiệm vụ do lỗi chủ quan, phạm lỗi lần đầu và chưa gây thiệt hại vật chất hoặc thiệt hại dưới 05 triệu đồng. Chậm nộp chưa tự chứng minh lỗi chủ quan: cần biết chứng từ được cung cấp lúc nào và trách nhiệm của các bên. Chưa ghi nhận tổn thất bằng tiền không đồng nghĩa đã xác minh không có mọi thiệt hại.",
        "conditions": ["Nộp báo cáo sau hạn: SATISFIED theo thời điểm mô tả.", "Lỗi chủ quan và phạm lỗi lần đầu: UNKNOWN.", "Mức thiệt hại thuộc điều kiện của quy định: cần xác minh; hồ sơ hiện chỉ nói chưa ghi nhận tổn thất bằng tiền."],
        "conclusion": "Chưa chốt hình thức kỷ luật. Xác minh thời điểm cung cấp chứng từ, nguyên nhân chậm nộp, lịch sử vi phạm và thiệt hại. Nếu điều kiện được xác nhận, đánh giá khả năng áp dụng quy định khiển trách bằng văn bản; không bịa quy định riêng về thời hạn báo cáo.",
        "questions": ["Loại hợp đồng và tình trạng gửi yêu cầu giải trình?", "Chứng từ cần thiết được cung cấp vào lúc nào?", "Phần chậm trễ nào do nhân viên chịu trách nhiệm?", "Đây có phải lỗi lần đầu và có thiệt hại vật chất đã xác minh không?"],
        "checks": ["Không đồng nhất chậm nộp với lỗi chủ quan", "Giữ đúng hạn và thời điểm gửi", "Không bịa chính sách báo cáo riêng"],
    },
    {
        "id": "CA04", "file": "04_Bien_ban_roi_vi_tri_lam_viec.docx",
        "name": "PHẠM THỊ DUNG", "employee_code": "EMP-034",
        "job": "Nhân viên chăm sóc khách hàng", "department": "Chăm sóc khách hàng",
        "family": "GENERAL", "event_date": "2026-10-14", "event_end": "2026-10-14", "minutes_date": "2026-10-15",
        "facts": {"violation_summary": "Rời quầy hỗ trợ từ 14:00 đến 15:10 ngày 14/10/2026, chưa xin phép, thông báo hoặc bàn giao; lịch nghỉ giữa ca cần xác minh.", "minutes_made": "true"},
        "unknown": ["contract_type", "explanation_requested", "first_offense", "break_schedule"],
        "rules": [("NQCT", "11"), ("BLLD_2019", "124")],
        "finding": "Khoảng 14:00–15:10 là 70 phút. Điều 11 nội quy có quy định khiển trách bằng văn bản với phạm lỗi lần đầu, tự ý rời vị trí trong ca quá 60 phút mà không được quản lý đồng ý. Hồ sơ mô tả chưa xin phép và chưa bàn giao; tuy nhiên lịch nghỉ giữa ca được nêu là chưa xác minh, và lịch sử vi phạm chưa có. Cần làm rõ liệu toàn bộ khoảng thời gian đã xác định là thời gian làm việc theo quy định áp dụng.",
        "conditions": ["Khoảng rời quầy theo đồng hồ lớn hơn 60 phút: SATISFIED (70 phút).", "Chưa được quản lý đồng ý: được mô tả trong hồ sơ.", "Phạm lỗi lần đầu và khoảng thời gian làm việc sau đối chiếu lịch nghỉ: UNKNOWN."],
        "conclusion": "Nêu khả năng áp dụng Điều 11 có điều kiện; chưa chốt mức khi lịch sử và lịch nghỉ chưa được xác nhận. Ghi nhận cam kết bàn giao không thay thế phân tích điều kiện và không tự xóa một vi phạm đã được chứng minh.",
        "questions": ["Loại hợp đồng và tình trạng gửi yêu cầu giải trình?", "Đây có phải lần đầu vi phạm không?", "Lịch nghỉ giữa ca và quy định bàn giao có áp dụng trong khoảng 14:00–15:10 không?"],
        "checks": ["Tính đúng 70 phút", "Đối chiếu ngưỡng quá 60 phút", "Không bịa lịch nghỉ hoặc lịch sử vi phạm"],
    },
    {
        "id": "CA05", "file": "05_Bien_ban_khong_tuan_thu_an_toan.docx",
        "name": "HOÀNG VĂN EM", "employee_code": "EMP-047",
        "job": "Nhân viên kho", "department": "Kho vận",
        "family": "GENERAL", "event_date": "2026-10-15", "event_end": "2026-10-15", "minutes_date": "2026-10-16",
        "facts": {"violation_summary": "Vào khu vực nhập hàng lúc 09:15 ngày 15/10/2026 khi chưa mang giày bảo hộ đã cấp; bổ sung trang bị sau yêu cầu dừng của giám sát, trước khi tiếp tục.", "minutes_made": "true"},
        "unknown": ["contract_type", "explanation_requested", "safety_training_record", "applicable_sanction_mapping"],
        "rules": [("NQCT", "7"), ("NQCT", "10"), ("BLLD_2019", "122"), ("BLLD_2019", "124")],
        "finding": "Điều 7 nội quy yêu cầu tuân thủ an toàn và sử dụng phương tiện bảo vệ cá nhân đã cấp. Việc không mang giày đã cấp phù hợp với vấn đề cần đối chiếu; nhân viên đã khắc phục tại chỗ. Trong các điều nội quy của snapshot chưa có quy định gắn riêng hành vi này với một hình thức kỷ luật cụ thể. Điều 10 nội quy và Điều 124 chỉ liệt kê hình thức, không tự tạo điều kiện áp dụng cho vi phạm bảo hộ.",
        "conditions": ["Không sử dụng giày đã cấp tại thời điểm vào khu vực: được mô tả và nhân viên thừa nhận.", "Đã khắc phục trước khi tiếp tục: được mô tả.", "Quy định gắn hành vi này với một hình thức kỷ luật cụ thể: NOT_SUPPORTED bởi các đoạn tham chiếu hiện có.", "Hồ sơ hướng dẫn an toàn: UNKNOWN."],
        "conclusion": "Chưa đủ căn cứ retrieval để xác định mức xử lý. Không tự chọn khiển trách, sa thải hay phạt tiền. Có thể đề nghị rà soát đào tạo và trang bị, nhưng không gọi đào tạo lại là thủ tục bắt buộc có căn cứ nếu không có đoạn hỗ trợ. Nếu truy xuất thêm nguồn hợp lệ trực tiếp quy định hình thức cho hành vi, phải đánh giá lại theo nguồn đó.",
        "questions": ["Loại hợp đồng và tình trạng gửi yêu cầu giải trình?", "Có hồ sơ hướng dẫn an toàn và quy trình áp dụng tại khu vực không?", "Có điều khoản còn hiệu lực quy định hình thức xử lý đối với hành vi cụ thể này không?"],
        "checks": ["Phân biệt nghĩa vụ PPE với căn cứ chọn mức", "Không coi đã khắc phục là chưa từng vi phạm", "Không bịa mức xử lý hoặc thủ tục đào tạo bắt buộc"],
    },
]


def extract(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        # Table cell paragraphs are retained in document order.
        return [text for p in root.findall(".//w:body//w:p", NS)
                if (text := "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip())]


def narrative(paragraphs: list[str]) -> str:
    prefixes = ("- Thời gian, địa điểm", "- Diễn biến", "•", "- Thiệt hại", "- Ý kiến của người bị")
    lines = [p for p in paragraphs if p.startswith(prefixes)]
    witness = next(p for p in paragraphs if p.startswith("- Ý kiến của người làm chứng"))
    # Keep witness confirmation; omit HR's proposed next action (target leakage).
    lines.append(witness.split("; Nhân sự", 1)[0] + ".")
    return "\n".join(lines)


def context_text(row: dict) -> str:
    location = "Điều " + row["article"]
    if row["clause"]:
        location += ", khoản " + row["clause"]
    return f"[{row['policy_code']} — {location}; chunk_id={row['chunk_id']}]\n{row['content']}"


def reference(case: dict, description: str, evidence: list[dict]) -> str:
    rules = "\n".join(f"- {r['policy_code']}, Điều {r['article']}"
                      + (f", khoản {r['clause']}" if r["clause"] else "")
                      + f"; evidence_id={r['chunk_id']}" for r in evidence)
    questions = "\n".join("- " + q for q in case["questions"])
    status = "NOT_SUPPORTED" if case["id"] == "CA05" else "NEED_MORE_FACTS"
    return f"""BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC

I. THÔNG TIN VỤ VIỆC
Nhân viên: {case['name']}; mã: {case['employee_code']}; chức danh: {case['job']}; bộ phận: {case['department']}. Ngày xảy ra dùng cho fixture: {case['event_date']}; khoảng sự việc đến {case['event_end']}. Nhóm: {case['family']}. Loại hợp đồng: chưa có. Ngày biên bản nguồn: {case['minutes_date']}; không dùng ngày họp thay ngày xảy ra.

II. TÌNH TIẾT ĐÃ XÁC NHẬN TRONG BỘ KIỂM THỬ
{description}
Các lời trình bày được xác nhận là đã được ghi nhận, không mặc nhiên xác nhận mọi nội dung giải thích là sự thật đã chứng minh.

III. TÌNH TIẾT CHƯA XÁC ĐỊNH
{questions}

IV. KẾT QUẢ ĐÁNH GIÁ
Trạng thái tham chiếu với gói chứng cứ được chỉ định: {status}. Mức chốt: chưa xác định.
{case['finding']}

V. CĂN CỨ ĐÁNH GIÁ
{rules}
Đây là căn cứ trong snapshot được chỉ định, không phải tuyên bố rằng hệ thống đã truy xuất đủ các đoạn này. Nghị định xử phạt hành chính hoặc tiền lệ không tự quyết định mức kỷ luật nhân viên.

VI. PHÂN TÍCH ĐIỀU KIỆN
{chr(10).join('- ' + c for c in case['conditions'])}

VII. QUY TRÌNH XỬ LÝ
Biên bản đã tồn tại tại thời điểm giả lập sau ngày lập biên bản. Việc đã gửi yêu cầu giải trình chính thức: chưa xác định. Điều 122 Bộ luật Lao động yêu cầu chứng minh lỗi và bảo đảm thủ tục được nêu trong điều khoản; Điều 14 và 15 nội quy là căn cứ đối chiếu biên bản và cuộc họp. Không kết luận đã hoàn thành toàn bộ thủ tục chỉ vì có biên bản. Chưa đủ thông tin về thông báo cuộc họp, thành phần bắt buộc, thời hiệu và thẩm quyền để xác nhận sẵn sàng ban hành.

VIII. RỦI RO CĂN CỨ
HIGH trong fixture chưa đủ tình tiết/căn cứ chốt mức. Không tự phê duyệt hoặc ban hành quyết định.

IX. CÁC ĐIỂM CẦN HR XÁC NHẬN
{questions}

X. KẾT LUẬN ĐỂ HR XEM XÉT
{case['conclusion']}

XI. QUYẾT ĐỊNH CỦA HR
HR lựa chọn: đồng ý với đánh giá; yêu cầu bổ sung thông tin; gửi hồ sơ cho pháp chế; hoặc không sử dụng kết quả đánh giá. Báo cáo không có nghĩa hồ sơ đã được gửi, ký hay đóng.
"""


def main() -> None:
    snapshot = json.loads((HERE / "policy_snapshot.json").read_text(encoding="utf-8"))
    samples, metadata = [], []
    for case in CASES:
        path = ROOT / "tested_golden_dataset" / case["file"]
        paragraphs = extract(path)
        description = narrative(paragraphs)
        full_description = (f"Nhân viên: {case['name']}; mã: {case['employee_code']}; "
                            f"chức danh: {case['job']}; bộ phận: {case['department']}.\n" + description)
        # Add procedure evidence to every reference, choosing clause 1 when split.
        targets = set(map(tuple, case["rules"])) | {("NQCT", "14"), ("NQCT", "15"), ("BLLD_2019", "122")}
        evidence = [r for r in snapshot["passages"]
                    if (r["policy_code"], r["article"]) in targets
                    and (r["article"] != "122" or r["clause"] == "1")]
        found = {(r["policy_code"], r["article"]) for r in evidence}
        if found != targets:
            raise ValueError(f"Missing reference evidence for {case['id']}: {targets - found}")
        for row in evidence:
            if row["effective_from"] > case["event_date"] or (row["effective_to"] and row["effective_to"] < case["event_date"]):
                raise ValueError(f"Out-of-date reference evidence for {case['id']}")
        user_input = (
            "Hãy đánh giá vụ việc dựa trên tình tiết dưới đây và các đoạn quy định được cung cấp. "
            "Nêu điều kiện đã đáp ứng, chưa đáp ứng, chưa xác định; căn cứ; mức đề xuất nếu đủ căn cứ; rủi ro và bước tiếp theo. "
            "Không tự bổ sung tình tiết, không ban hành quyết định.\n\n"
            "Bối cảnh bộ kiểm thử: An Phát là tên giả của doanh nghiệp áp dụng NQCT/HRCorp trong snapshot đi kèm. "
            "Đây là đánh giá trực tiếp gói tình tiết chưa đầy đủ, không phải lượt chat tự động vượt qua cổng xác nhận. "
            f"Thời điểm giả lập: sau khi lập biên bản ngày {case['minutes_date']}.\n"
            f"Ngày xảy ra dùng để chọn phiên bản: {case['event_date']}; khoảng sự việc đến {case['event_end']}.\n"
            f"Nhóm vụ việc: {case['family']}.\n\n"
            "TÌNH TIẾT NGUỒN\n" + full_description + "\n\n"
            "FACT ĐÃ CHUẨN HÓA TỪ NGUỒN\n" + json.dumps(case["facts"], ensure_ascii=False, indent=2)
            + "\n\nCHƯA XÁC ĐỊNH\n" + ", ".join(case["unknown"])
        )
        samples.append({
            "user_input": user_input,
            "reference": reference(case, full_description, evidence),
            "reference_contexts": [context_text(r) for r in evidence],
            "response": None,
            "retrieved_contexts": None,
        })
        metadata.append({
            "case_id": case["id"], "row_index": len(samples) - 1,
            "source_file": str(path.relative_to(ROOT)),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_paragraphs": paragraphs,
            "source_conclusion": [p for p in paragraphs if p.startswith(("- Kết quả đánh giá", "- Hình thức xử lý đề xuất"))],
            "model_description": full_description,
            "family": case["family"], "incident_date": case["event_date"],
            "incident_end_date": case["event_end"], "minutes_date": case["minutes_date"],
            "source_known_facts": case["facts"], "unknown_facts": case["unknown"],
            "normal_workflow_ready": False,
            "normal_workflow_blocker": "contract_type missing; remaining required facts must be explicitly confirmed",
            "reference_status": "draft_pending_expert_review",
            "reference_origin": "Assistant-authored condition analysis from extracted source and frozen corpus; not verbatim source assessment",
            "expected_assessment_status_with_reference_contexts": "NOT_SUPPORTED" if case["id"] == "CA05" else "NEED_MORE_FACTS",
            "expected_sanction_type": None,
            "expected_checks": case["checks"],
            "reference_evidence_ids": [r["chunk_id"] for r in evidence],
            "normalization_notes": [
                "Event start selected as incident_date; full interval retained.",
                "minutes_made=true is valid only in the declared post-minutes simulation.",
                "Source statements are observations/test facts, not externally verified evidence.",
                "An Phát-to-HRCorp alias is a declared fixture assumption, not a source fact.",
            ],
        })
    manifest = {
        "version": 1, "task": "case_assessment", "sample_count": len(samples),
        "evaluation_scope": "Direct incomplete-case assessment; production chat must clarify missing required facts first",
        "reference_status": "draft_pending_expert_review",
        "ragas_schema_source": "https://docs.ragas.io/en/latest/references/evaluation_schema/",
        "policy_snapshot": "policy_snapshot.json",
        "case_ids_in_row_order": [c["id"] for c in CASES],
        "cases": metadata,
    }
    for name, value in [("ragas_dataset.json", samples), ("source_metadata.json", manifest)]:
        (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(samples)} cases; wrote ragas_dataset.json and source_metadata.json")


if __name__ == "__main__":
    main()
