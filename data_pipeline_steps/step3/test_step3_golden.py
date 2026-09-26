"""8 Golden Test Cases Buoc 3 (Phan D) - chay tren du lieu cleaned that."""
import unittest

from data_pipeline_steps.step3.hierarchy_parser import (
    parse_document, load_cleaned, parse_article_content,
)
from data_pipeline_steps.step3.chunking_engine import (
    ChunkingEngine, apply_formula_patch,
)
from data_pipeline_steps.step3.cross_reference_resolver import (
    resolve_cross_references, DocScope,
)
from data_pipeline_steps.step3.run_step3 import STEP3_DIR

STEMS = {
    "BLLD": "2026_131_18_VBHN-VPQH",
    "ND145": "nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong",
    "ND283": "283_2026_ND-CP_642116",
}
_trees = {}
_chunks = {}
_engine = ChunkingEngine()


def get_tree(key):
    if key not in _trees:
        text = load_cleaned(STEMS[key])
        if key == "ND145":
            text, _ = apply_formula_patch(
                text, str(STEP3_DIR / "formulas_patch.json"))
        _trees[key] = parse_document(text, STEMS[key])
    return _trees[key]


def get_chunks(key):
    if key not in _chunks:
        _chunks[key] = _engine.chunk_document(get_tree(key))
    return _chunks[key]


def find_article(tree, number, chapter_canon=None):
    for ch, sec, a in tree.all_articles():
        if a.number == number and (chapter_canon is None
                                   or ch.canonical == chapter_canon):
            return ch, sec, a
    return None, None, None


class TestStep3Golden(unittest.TestCase):
    def test_tc1_chapeau_inheritance_nd145_d3(self):
        tree = get_tree("ND145")
        ch, sec, a = find_article(tree, 3)
        self.assertIsNotNone(a)
        pa = parse_article_content(a.raw_body)
        self.assertTrue(pa.chapeau and "sổ quản lý lao động" in pa.chapeau)
        chunks = [c for c in get_chunks("ND145")
                  if c.metadata.article_number == 3]
        # Dieu 3 ngan -> gom 1 chunk ARTICLE, nhung chapeau phai con nguyen
        self.assertTrue(chunks)
        for c in chunks:
            blob = (c.metadata.chapeau_text or "") + "\n" + c.text
            self.assertIn("sổ quản lý lao động", blob)
        # Ke thua o cap Khoan: kiem tra truc tiep qua parse
        self.assertGreaterEqual(len(pa.clauses), 3)

    def test_tc2_no_section_blld_d1(self):
        # HIEU CHINH vs plan: Dieu 106 THUC TE nam trong Muc 1 Chuong VII
        # (plan ghi sai 'Chuong VII khong chia Muc'). Dung Dieu 1 Chuong I
        # (that su khong Muc) de kiem tra section=null.
        tree = get_tree("BLLD")
        ch, sec, a = find_article(tree, 1)
        self.assertIsNotNone(a)
        self.assertIsNone(sec)
        self.assertEqual(ch.raw, "I")
        chunks = [c for c in get_chunks("BLLD")
                  if c.metadata.article_number == 1]
        self.assertTrue(chunks)
        for c in chunks:
            self.assertIsNone(c.metadata.section_number)
            self.assertIsNone(c.metadata.section_title)
            self.assertIn("CHƯƠNG I", c.header_context)
            self.assertNotIn("MỤC", c.header_context)

    def test_tc3_duplicate_chapter_nd145_d114(self):
        tree = get_tree("ND145")
        ch, sec, a = find_article(tree, 114, chapter_canon="XII")
        self.assertIsNotNone(a, "Dieu 114 phai thuoc chuong canonical XII")
        self.assertEqual(ch.raw, "XI")
        self.assertEqual(ch.chapter_title if hasattr(ch, "chapter_title") else ch.title,
                         "ĐIỀU KHOẢN THI HÀNH")
        self.assertTrue(any("DUPLICATE_CHAPTER_NUMBER" in f
                            for f in ch.anomaly_flags))
        chunks = [c for c in get_chunks("ND145")
                  if c.metadata.article_number == 114]
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].metadata.chapter_canonical, "XII")

    def test_tc4_long_article_blld_d219(self):
        chunks = [c for c in get_chunks("BLLD")
                  if c.metadata.article_number == 219]
        # 9 Khoan -> toi thieu 9 chunk, id duy nhat (khong trung do trich dan)
        self.assertGreaterEqual(len(chunks), 9)
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)), "trung chunk_id!")
        for c in chunks:
            self.assertLessEqual(c.metadata.token_count, _engine.max_tokens,
                                 f"chunk {c.chunk_id} vuot nguong")
            self.assertIn("CHƯƠNG XVII", c.header_context)
            self.assertIn("219", c.chunk_id)

    def test_tc5_atomic_penalty_unit_nd283_d49(self):
        chunks = [c for c in get_chunks("ND283")
                  if c.metadata.article_number == 49
                  and c.metadata.clause_number == 1
                  and c.metadata.chunk_level == "POINT"]
        self.assertGreaterEqual(len(chunks), 11)
        for c in chunks:
            self.assertIn("Phạt tiền từ 10.000.000", c.header_context)
            self.assertEqual(c.metadata.penalty_min_vnd, 10000000)
            self.assertIn("Điểm", c.text)

    def test_tc6_interdoc_ref_nd145_d1(self):
        tree = get_tree("ND145")
        ch, sec, a = find_article(tree, 1)
        pa = parse_article_content(a.raw_body)
        k2 = [c for c in pa.clauses if c.number == 2][0]
        scope = DocScope(document_id="145/2020/NĐ-CP", max_article=115,
                         scoped_to_blld=True)
        refs = resolve_cross_references(k2.text_with_points, scope)
        targets = {(r.target_doc, r.article) for r in refs}
        self.assertIn(("18/VBHN-VPQH", 21), targets)
        self.assertIn(("18/VBHN-VPQH", 35), targets)
        self.assertFalse(any(t == "145/2020/NĐ-CP" and art in (21, 35)
                             for t, art in targets))

    def test_tc7_missing_formula_nd145_d56(self):
        chunks = [c for c in get_chunks("ND145")
                  if c.metadata.article_number == 56]
        self.assertTrue(chunks, "Dieu 56 phai van tao chunk, khong crash")
        flagged = [c for c in chunks
                   if "MISSING_FORMULA_IMAGE" in c.metadata.anomaly_flags]
        self.assertTrue(flagged)

    def test_tc8_footnote_amended_blld_d59(self):
        # HIEU CHINH vs plan: anchor 'a)2[[2]]' THUC TE nam o Dieu 59
        # (plan ghi nham Dieu 61). Muc parse + chunk deu phai dung.
        from data_pipeline_steps.step3.hierarchy_parser import parse_article_content as _pac
        tree = get_tree("BLLD")
        ch, sec, a = find_article(tree, 59)
        self.assertIsNotNone(a)
        pa = _pac(a.raw_body)
        pts_a = [p for cl in pa.clauses for p in cl.points
                 if p.letter == "a" and 2 in p.footnote_ids]
        self.assertTrue(pts_a, "Diem a phai parse dung 'a' + giu footnote 2")
        chunks = [c for c in get_chunks("BLLD")
                  if c.metadata.article_number == 59
                  and (c.metadata.amended_by or {}).get("law_no") == "124/2025/QH15"]
        self.assertTrue(chunks, "chunk Dieu 59 phai mang amended_by")
        c = chunks[0]
        self.assertEqual(c.metadata.effective_status, "AMENDED")
        self.assertEqual(c.metadata.amended_by["effective_date"], "2026-01-01")

    def test_tc9_explicit_other_code_blld_d219(self):
        # 'Dieu 32 cua Bo luat To tung dan su so 92/2015/QH13' -> target
        # 92/2015/QH13, TUYET DOI khong gan nham self Dieu 32 BLLD.
        from data_pipeline_steps.step3.cross_reference_resolver import (
            resolve_cross_references as _resolve, DocScope as _Scope)
        text = ("2. Sửa đổi, bổ sung Điều 32 của Bộ luật Tố tụng dân sự "
                "số 92/2015/QH13 như sau:")
        refs = _resolve(text, _Scope(document_id="18/VBHN-VPQH",
                                     max_article=220))
        targets = {(r.target_doc, r.article, r.rule) for r in refs}
        self.assertIn(("92/2015/QH13", 32, "EXPLICIT"), targets)
        self.assertFalse(any(t == "18/VBHN-VPQH" and art == 32
                             for t, art, _ in targets))


if __name__ == "__main__":
    unittest.main()
