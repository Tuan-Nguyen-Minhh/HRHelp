"""Tạo nhãn retrieval nháp từ ảnh chụp corpus, trước khi chạy truy xuất.

Các nhóm điều/khoản được chọn thủ công theo nội dung, không lấy từ thứ hạng của
retriever. Đây là tập chứng cứ tối thiểu được gán nhãn, chưa phải bộ căn cứ đủ
để ra quyết định pháp lý.
"""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .snapshot import HERE, fingerprint

ROOT = Path(__file__).resolve().parents[2]
UNITS = {
    "L118": ("BLLD_2019", 118, None, None, "authority", "Nội quy và hành vi phải được quy định"),
    "L122_1": ("BLLD_2019", 122, 1, None, "procedure", "Nguyên tắc chứng minh lỗi và thành phần tham gia"),
    "L122_4": ("BLLD_2019", 122, 4, None, "exception", "Các thời gian không được xử lý kỷ luật"),
    "L122_5": ("BLLD_2019", 122, 5, None, "exception", "Mất khả năng nhận thức hoặc điều khiển hành vi"),
    "L123": ("BLLD_2019", 123, None, None, "procedure", "Thời hiệu xử lý kỷ luật"),
    "L124": ("BLLD_2019", 124, None, None, "authority", "Các hình thức xử lý kỷ luật"),
    "L125": ("BLLD_2019", 125, None, None, "authority", "Các điều kiện và ngoại lệ của hình thức sa thải"),
    "L126": ("BLLD_2019", 126, None, None, "condition", "Xóa kỷ luật và giảm thời hạn chấp hành"),
    "L127": ("BLLD_2019", 127, None, None, "exception", "Các hành vi bị nghiêm cấm khi xử lý kỷ luật"),
    "L129": ("BLLD_2019", 129, None, None, "authority", "Bồi thường thiệt hại"),
    "L130": ("BLLD_2019", 130, None, None, "condition", "Nguyên tắc xử lý bồi thường thiệt hại"),
    "N4": ("NQCT", 4, None, None, "condition", "Báo vắng và trường hợp đột xuất theo nội quy đang lưu"),
    "N6": ("NQCT", 6, None, None, "internal_rule", "Tài sản và bí mật kinh doanh"),
    "N7": ("NQCT", 7, None, None, "internal_rule", "An toàn và trang bị bảo hộ"),
    "N8": ("NQCT", 8, None, None, "internal_rule", "Quấy rối tình dục theo nội quy"),
    "N10": ("NQCT", 10, None, None, "internal_rule", "Các hình thức và cấm phạt tiền thay kỷ luật"),
    "N11": ("NQCT", 11, None, None, "internal_rule", "Hành vi và điều kiện khiển trách đang lưu"),
    "N12": ("NQCT", 12, None, None, "internal_rule", "Điều kiện kéo dài nâng lương hoặc cách chức"),
    "N13": ("NQCT", 13, None, None, "internal_rule", "Điều kiện và lý do chính đáng theo nội quy"),
    "N14": ("NQCT", 14, None, None, "procedure", "Lập biên bản và chứng cứ"),
    "N15": ("NQCT", 15, None, None, "procedure", "Thông báo và họp xử lý kỷ luật"),
    "N16": ("NQCT", 16, None, None, "procedure", "Thẩm quyền ban hành quyết định"),
    "N17": ("NQCT", 17, None, None, "internal_rule", "Trách nhiệm vật chất"),
    "N18": ("NQCT", 18, None, None, "procedure", "Thời hiệu và xóa kỷ luật theo nội quy"),
    "D69_i": ("ND145_2020", 69, 2, "i", "procedure", "Người có thẩm quyền theo nguồn đang lưu"),
    "D70_1": ("ND145_2020", 70, 1, None, "procedure", "Phát hiện và lập biên bản"),
    "D70_a": ("ND145_2020", 70, 2, "a", "procedure", "Thông báo trước cuộc họp"),
    "D70_3": ("ND145_2020", 70, 3, None, "procedure", "Biên bản cuộc họp và chữ ký"),
    "D84_1": ("ND145_2020", 84, 1, None, "condition", "Định nghĩa quấy rối tình dục"),
    "D84_3": ("ND145_2020", 84, 3, None, "condition", "Phạm vi nơi làm việc"),
}


def eligible(chunk, day):
    return (
        chunk["is_active"]
        and not chunk["policy_deleted"]
        and not chunk["document_deleted"]
        and chunk["ingest_status"] in {"CHUNKED", "EMBEDDED"}
        and chunk["version_status"] == "ACTIVE"
        and chunk["effective_from"] <= day
        and (chunk["effective_to"] is None or chunk["effective_to"] >= day)
    )


def source_excerpt(filename):
    path = ROOT / "golden_dataset" / filename
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    selected = []
    for i, paragraph in enumerate(root.findall(".//w:p", ns)):
        text = "".join(t.text or "" for t in paragraph.findall(".//w:t", ns)).strip()
        if "Diễn biến sự việc:" in text:
            selected.append({"paragraph_index": i + 1, "text": text})
    if len(selected) != 1:
        raise ValueError(f"Cần rà soát trích đoạn {filename}")
    return selected[0]["text"], {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "paragraphs": selected,
    }


def build(snapshot):
    if fingerprint(snapshot) != snapshot["corpus_sha256"]:
        raise ValueError("Ảnh chụp corpus không khớp mã băm")
    units = {}
    for key, (code, article, clause, point, role, reason) in UNITS.items():
        rows = [
            c
            for c in snapshot["chunks"]
            if c["policy_code"] == code
            and c["article"] == str(article)
            and (clause is None or c["clause"] == str(clause))
            and (point is None or c["point"] == point)
        ]
        if not rows:
            raise ValueError(f"Không tìm thấy đơn vị chứng cứ {key}; không tự bỏ nhãn")
        rows.sort(key=lambda c: c["chunk_index"])
        units[key] = {
            "policy_code": code,
            "article": article,
            "clause": clause,
            "point": point,
            "role": role,
            "reason_vi": reason,
            "member_ids": [c["chunk_id"] for c in rows],
            "member_hashes": {c["chunk_id"]: c["content_sha256"] for c in rows},
        }
    cases = []

    def add(
        key,
        text,
        bundles,
        critical=(),
        *,
        day="2026-10-16",
        family="GENERAL",
        facts=None,
        support=(),
        source=None,
        empty=False,
        note="",
    ):
        relevant = {unit for bundle in bundles for unit in bundle}
        judgments = {chunk_id: 3 for unit in relevant for chunk_id in units[unit]["member_ids"]}
        for unit in support:
            for chunk_id in units[unit]["member_ids"]:
                judgments.setdefault(chunk_id, 1)
        # Explicit, limited negative pool: overseas-worker administrative fines
        # are not direct employee disciplinary grounds for these labeled tasks.
        for c in snapshot["chunks"]:
            if c["policy_code"] == "ND283_2026" and c["article"] in {"49", "50"}:
                judgments.setdefault(c["chunk_id"], 0)
        rows_by_id = {c["chunk_id"]: c for c in snapshot["chunks"]}
        for unit in relevant | set(critical) | set(support):
            if not all(eligible(rows_by_id[i], day) for i in units[unit]["member_ids"]):
                raise ValueError(f"{key}: nhãn {unit} không đủ điều kiện tại ngày {day} theo metadata hiện tại")
        cases.append(
            {
                "case_id": key,
                "reference_status": "draft_pending_expert_review",
                "reviewer": None,
                "origin": "source_excerpt" if source else "synthetic_source_task",
                "source": source,
                "input": {
                    "query": text,
                    "description": text,
                    "family": family,
                    "facts": facts or {},
                    "incident_date": day,
                },
                "date_origin": "synthetic_fixture_not_legal_validation",
                "evidence_bundles": bundles,
                "critical_units": list(critical),
                "judgments": judgments,
                "expected_empty": empty,
                "note_vi": note,
            }
        )

    source_tasks = [
        ("01_Bien_ban_nghi_khong_phep.docx", ["N13", "L125"], ["N13", "L125"], "UNAUTHORIZED_ABSENCE"),
        ("02_Bien_ban_di_muon.docx", ["N11", "L118"], ["N11"], "LATE"),
        ("03_Bien_ban_cham_nop_bao_cao.docx", ["N11", "L118"], ["N11"], "GENERAL"),
        ("04_Bien_ban_roi_vi_tri_lam_viec.docx", ["N11", "L118"], ["N11"], "GENERAL"),
        ("05_Bien_ban_khong_tuan_thu_an_toan.docx", ["N7", "L118"], ["N7"], "GENERAL"),
    ]
    for n, (filename, bundle, critical, family) in enumerate(source_tasks, 1):
        excerpt, source = source_excerpt(filename)
        add(
            f"S{n:02}",
            excerpt + "\nTìm căn cứ nội quy và pháp luật, kèm điều kiện cần kiểm tra trước khi đề xuất xử lý.",
            [bundle],
            critical,
            family=family,
            support=("L122_1", "N14", "N15"),
            source=source,
            note="Câu sự việc lấy từ DOCX; câu yêu cầu tìm căn cứ và ngày truy xuất là giả lập. Bộ căn cứ được gán nhãn chỉ là mức tối thiểu để chẩn đoán retrieval.",
        )
    add(
        "Q06",
        "Nhân viên tự ý nghỉ 3 ngày trong 30 ngày. Tìm điều kiện theo nội quy, cách báo vắng và nền tảng pháp luật.",
        [["N12", "N4", "L118"]],
        ["N12", "N4"],
        family="UNAUTHORIZED_ABSENCE",
    )
    add(
        "Q07",
        "Nghỉ 5 ngày trong 30 ngày vì bản thân bị ốm có giấy xác nhận. Cần kiểm tra ngoại lệ lý do chính đáng trong nội quy và Bộ luật Lao động.",
        [["N13", "L125"]],
        ["N13", "L125"],
        family="UNAUTHORIZED_ABSENCE",
    )
    add(
        "Q08",
        "Nhân viên chuyển dữ liệu khách hàng cho bên thứ ba khi không có nhiệm vụ. Tìm quy định về bí mật và điều kiện xử lý.",
        [["N6", "N13", "L125"]],
        ["N6", "L125"],
    )
    add(
        "Q09",
        "Hành vi quấy rối tình dục xảy ra trong chuyến công tác. Tìm định nghĩa, phạm vi nơi làm việc, nội quy và điều kiện áp dụng.",
        [["N8", "L125", "D84_1", "D84_3"]],
        ["D84_3"],
        day="2026-08-15",
    )
    add(
        "Q10",
        "Cần kiểm tra trường hợp chưa được xử lý kỷ luật: người lao động đang mang thai hoặc mất khả năng nhận thức do bệnh.",
        [["L122_4", "L122_5"]],
        ["L122_4", "L122_5"],
    )
    add(
        "Q11",
        "Có được phạt tiền hoặc cắt lương thay cho xử lý kỷ luật lao động không? Tìm điều cấm trong luật và nội quy.",
        [["L127", "N10"]],
        ["L127"],
    )
    add(
        "Q12",
        "Tìm thời hiệu xử lý kỷ luật thông thường và trường hợp liên quan tài chính, tài sản, bí mật kinh doanh theo luật và nội quy.",
        [["L123", "N18"]],
        ["L123"],
    )
    add(
        "Q13",
        "Nhân viên đã bị kéo dài thời hạn nâng lương, nay lặp lại hành vi. Tìm điều kiện tái phạm và xóa kỷ luật trước khi đề xuất.",
        [["L126", "L125", "N13"]],
        ["L126"],
    )
    add(
        "Q14",
        "Liệt kê các hình thức xử lý kỷ luật được quy định trong Bộ luật Lao động và nội quy công ty.",
        [["L124", "N10"]],
        ["L124"],
    )
    notice = "Tìm quy định có nêu thời hạn thông báo trước cuộc họp xử lý kỷ luật lao động."
    add(
        "Q15",
        notice,
        [["N15"], ["D70_a"]],
        day="2026-09-09",
        note="Hai phương án đủ để trả lời câu hỏi hẹp về thời hạn thông báo; không yêu cầu hợp của hai phương án. Ngày hết hiệu lực tính cả ngày theo metadata ứng dụng.",
    )
    add(
        "Q16",
        "Khi phát hiện vi phạm và tổ chức họp kỷ luật, việc lập biên bản và chữ ký của người tham dự được quy định ra sao?",
        [["N14", "D70_1", "D70_3"]],
        ["D70_3"],
        day="2026-08-15",
        support=("L122_1",),
    )
    add(
        "Q17",
        "Ai có thẩm quyền xử lý và ký quyết định kỷ luật lao động theo nội quy và văn bản hướng dẫn?",
        [["N16", "D69_i"]],
        ["N16"],
        day="2026-08-15",
    )
    add(
        "Q18",
        "Người lao động sơ suất làm hỏng dụng cụ, thiệt hại không nghiêm trọng. Tìm trách nhiệm vật chất, mức bồi thường và nguyên tắc xem xét.",
        [["N17", "L129", "L130"]],
        ["L129"],
    )
    add(
        "Q19",
        notice,
        [["N15"]],
        ["N15"],
        day="2026-09-10",
        note="Cặp với Q15: ND145 không còn đủ điều kiện theo metadata DB sau 09/09/2026. Đây không phải xác nhận lịch sử hiệu lực pháp lý.",
    )
    add(
        "Q20",
        "Tìm căn cứ về xử lý kỷ luật lao động cho vụ việc này.",
        [],
        day="2000-01-01",
        empty=True,
        note="Ca âm tính có kiểm soát: không có chunk đủ điều kiện theo ngày trong corpus chụp. Không đồng nghĩa không tồn tại quy định pháp luật ngoài corpus.",
    )
    return {
        "schema_version": 1,
        "reference_status": "draft_pending_expert_review",
        "corpus_sha256": snapshot["corpus_sha256"],
        "units": units,
        "cases": cases,
        "scope_vi": "20 ca truy xuất; nhãn chứng cứ tối thiểu và mức liên quan là bản nháp. Không xác nhận căn cứ đủ để ra quyết định pháp lý.",
        "precision_scope_vi": "Nhãn liên quan chưa bao phủ toàn bộ corpus. Chunk chưa gán nhãn được báo riêng; không mặc nhiên kết luận không liên quan.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=HERE / "corpus_snapshot.json")
    parser.add_argument("--output", type=Path, default=HERE / "golden.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("Đã có nhãn; dùng --output khác hoặc --overwrite")
    data = build(json.loads(args.snapshot.read_text()))
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Đã tạo {len(data['cases'])} ca, {len(data['units'])} đơn vị chứng cứ nháp.")


if __name__ == "__main__":
    main()
