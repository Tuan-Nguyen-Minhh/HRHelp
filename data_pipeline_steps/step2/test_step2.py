"""
Unit tests for step 2 preprocessing logic
"""

import unittest
from pathlib import Path
from data_pipeline_steps.step2.step2_preprocessing import (
    pre_clean_text,
    extract_metadata,
    detect_boundaries,
    transform_structure,
    validate_articles,
    process_single_file,
)


class TestStep2Preprocessing(unittest.TestCase):
    def test_pre_clean_text(self):
        sample = "Điều\\_1.   Quy định   chung\ufeff"
        cleaned = pre_clean_text(sample)
        self.assertEqual(cleaned, "Điều_1. Quy định chung")

    def test_metadata_extraction_decree(self):
        text = (
            "Số: 283/2026/NĐ-CP\n"
            "**NGHỊ ĐỊNH**\n"
            "QUY ĐỊNH XỬ PHẠT VI PHẠM HÀNH CHÍNH\n\n"
            "*Căn cứ Luật...*\n"
        )
        meta = extract_metadata(text, "test.md")
        self.assertEqual(meta["document_number"], "283/2026/NĐ-CP")
        self.assertEqual(meta["document_type"], "NGHỊ ĐỊNH")
        self.assertTrue("QUY ĐỊNH XỬ PHẠT" in meta["document_title"])

    def test_structural_transformation_merge(self):
        lines = [
            "**Chương I**",
            "**QUY ĐỊNH CHUNG**",
            "",
            "**Điều 1.**",
            "**Phạm vi điều chỉnh**",
            "Nội dung quy định của điều 1.",
        ]
        transformed = transform_structure(lines)
        joined = "\n".join(transformed)
        self.assertIn("## Chương I. QUY ĐỊNH CHUNG", joined)
        self.assertIn("#### Điều 1. Phạm vi điều chỉnh", joined)

    def test_validation_success(self):
        text = "#### Điều 1. A\n#### Điều 2. B\n#### Điều 3. C"
        res = validate_articles(text, {})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["total_parsed_articles"], 3)
        self.assertEqual(res["max_article_number"], 3)
        self.assertEqual(len(res["missing_article_numbers"]), 0)

    def test_toc_bypass(self):
        # TOC without dots or numbers
        lines = [
            "MỤC LỤC",
            "Chương I. NHỮNG QUY ĐỊNH CHUNG",
            "Chương II. QUY ĐỊNH CỤ THỂ",
            "Điều 1. Nội dung A",
            "Điều 2. Nội dung B",
            "**CHƯƠNG I**",  # Real start
            "**NHỮNG QUY ĐỊNH CHUNG**",
            "**Điều 1.** Nội dung thật",
            "Đây là body text 1",
            "Đây là body text 2",
            "Đây là body text 3",
        ]
        start, end = detect_boundaries(lines)
        # Expected to skip the TOC lines and hit "**CHƯƠNG I**" (index 5)
        self.assertEqual(start, 5)

    def test_tail_boundary_long_signature(self):
        lines = [
            "**CHƯƠNG I**",  # Real start
            "**Điều 1.** Nội dung thật",
            "Đây là body text 1",
            "Đây là body text 2",
            "Đây là body text 3",
            "BỘ TRƯỞNG BỘ LAO ĐỘNG - THƯƠNG BINH VÀ XÃ HỘI",
            "Đào Ngọc Dung"
        ]
        start, end = detect_boundaries(lines)
        self.assertEqual(end, 5)

    def test_structural_transformation_wrapped_title(self):
        lines = [
            "**Chương I**",
            "**QUY ĐỊNH CHUNG DÀI**",
            "NÊN BỊ XUỐNG DÒNG",
            "**Điều 1.**",
            "**Phạm vi điều chỉnh dài**",
            "bị rớt xuống đây",
            "1. Nội dung quy định khoản 1.",
        ]
        transformed = transform_structure(lines)
        joined = "\n".join(transformed)
        self.assertIn("## Chương I. QUY ĐỊNH CHUNG DÀI NÊN BỊ XUỐNG DÒNG", joined)
        self.assertIn("#### Điều 1. Phạm vi điều chỉnh dài bị rớt xuống đây", joined)

    def test_phan_structure(self):
        lines = [
            "# Phần I. NHỮNG QUY ĐỊNH CHUNG",
            "## Chương I. QUY ĐỊNH CHUNG",
            "Nội dung chương 1.",
        ]
        transformed = transform_structure(lines)
        joined = "\n".join(transformed)
        self.assertIn("# Phần I.", joined)
        text = "# Phần I. A\n# Phần II. B"
        res = validate_articles(text + "\n#### Điều 1. X", {})
        counts = res.get("structure_counts", {})
        # validate với raw scope có Phần phải đếm đủ
        res2 = validate_articles(
            "# Title\n\n# Phần I. A",
            {},
            "# Phần I. A",
        )
        self.assertEqual(res2["structure_counts"]["phan"]["raw"], 1)
        self.assertEqual(res2["structure_counts"]["phan"]["final"], 1)

    def test_toc_short_two_items(self):
        lines = [
            "MỤC LỤC",
            "Chương I. ABC",
            "Chương II. DEF",
            "**CHƯƠNG I**",
            "**NHỮNG QUY ĐỊNH CHUNG**",
            "**Điều 1.** Nội dung thật",
            "Đây là nội dung body thật của điều 1 với đầy đủ ngữ cảnh pháp lý cần thiết",
            "Đây là body text 2 với nội dung giải thích thêm về quy định pháp luật",
        ]
        start, end = detect_boundaries(lines)
        self.assertEqual(start, 3)

    def test_same_line_title_continuation(self):
        lines = [
            "**Điều 3. Giải thích một số từ ngữ**",
            "chưa thành niên là người dưới 18 tuổi",
            "1. Nội dung khoản 1 của điều 3.",
        ]
        transformed = transform_structure(lines)
        joined = "\n".join(transformed)
        self.assertIn("#### Điều 3. Giải thích một số từ ngữ chưa thành niên", joined)

    def test_validation_warn_muc_phan(self):
        cleaned = "## CHƯƠNG I. A\n#### Điều 1. X"
        res = validate_articles(cleaned, {}, "MỤC 1. Foo\nMỤC 2. Bar\nCHƯƠNG I. A")
        warns = " ".join(res["warnings"])
        self.assertIn("Mục", warns)
        self.assertEqual(res["status"], "WARNING")

    def test_toc_short_no_heading_implicit(self):
        # Case B: TOC 2 mục, KHÔNG có dòng MỤC LỤC (MarkItDown rớt heading)
        lines_b = [
            "Chương I. NHỮNG QUY ĐỊNH CHUNG",
            "Chương II. QUY ĐỊNH CỤ THỂ",
            "**CHƯƠNG I**",
            "**NHỮNG QUY ĐỊNH CHUNG**",
            "**Điều 1.** Phạm vi điều chỉnh",
            "Nghị định này quy định chi tiết một số điều liên quan đến lao động và việc làm",
        ]
        start, end = detect_boundaries(lines_b)
        self.assertEqual(start, 2)


if __name__ == "__main__":
    unittest.main()
