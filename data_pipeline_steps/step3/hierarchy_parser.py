"""Hierarchy Parser + article-content splitter (plan 3.2).

Doc cleaned_markdown -> DocumentTree (chuong/muc/dieu + raw bodies),
tach chapeau khoi heading, tach khoan/diem, xu ly 'Khoan 1 ngam',
go footnote dinh nghia ra khoi body Dieu cuoi.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .schema import (
    ArticleNode, SectionNode, ChapterNode, DocumentTree,
)
from .anomaly_detector import (
    ChapterTracker, detect_section_anomaly,
    split_merged_footnote, has_formula_placeholder,
)

# ---- Anh xa dinh danh chuan (Edge D: document_number trong metadata_summary bi lech) ----
DOC_ID_MAP = {
    "2026_131_18_VBHN-VPQH": {
        "document_id": "18/VBHN-VPQH", "document_type": "BO_LUAT",
        "document_form": "VAN_BAN_HOP_NHAT", "doc_code": "BLLD",
        "max_article": 220,
    },
    "283_2026_ND-CP_642116": {
        "document_id": "283/2026/NĐ-CP", "document_type": "NGHI_DINH",
        "document_form": "VAN_BAN_GOC", "doc_code": "ND283_2026",
        "max_article": 68,  # ground truth sau khi va tail-cut (khong phai 65)
    },
    "nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong": {
        "document_id": "145/2020/NĐ-CP", "document_type": "NGHI_DINH",
        "document_form": "VAN_BAN_GOC", "doc_code": "ND145_2020",
        "max_article": 115,
    },
    "noi_quy_mau_cong_ty": {
        "document_id": "NQLD-HRCORP-2026", "document_type": "NOI_QUY",
        "document_form": "VAN_BAN_NOI_BO", "doc_code": "NQCT",
        # 100 Dieu sau dot bo sung cac ho quy trinh tu noi quy thuc te (2026-10). Gia tri nay
        # chi de doi chieu canh bao; run_step3 lay max thuc te tu cay.
        "max_article": 100,
    },
}

CHAP_RE = re.compile(r"^##\s+Chương\s+([IVXLCDM]+)\b[\.:]?\s*(.*)$", re.IGNORECASE)
SEC_RE = re.compile(r"^###\s+Mục\s+(\d+)\b[\.:]?\s*(.*)$", re.IGNORECASE)
ART_RE = re.compile(r"^####\s*Điều\s+(\d+)[a-z]?\b[\.:]?\s*(.*)$", re.IGNORECASE)
PHAN_RE = re.compile(r"^#\s+Phần\s+[IVXLCDM\d]+", re.IGNORECASE)

CLAUSE_RE = re.compile(r"^\s*(\d+)\.\s+(.*)$")
POINT_RE = re.compile(
    r"^\s*([a-zđ]\d*)\)\s*(?:\[\[\d+\]\]\(#footnote-\d+\))?\s*(.*)$",
    re.IGNORECASE,
)

# Cum tu bao hieu cau dan (chapeau) bi dinh vao tieu de Dieu
CHAPEAU_TRIGGERS = [
    "như sau:", "như sau :", "quy định như sau", "được hiểu như sau",
    "được quy định như sau", "bao gồm:", "gồm các", "cụ thể như sau",
]

TAIL_TABLE_RE = re.compile(
    r"VĂN PHÒNG QUỐC HỘI|XÁC THỰC VĂN BẢN HỢP NHẤT", re.IGNORECASE
)
FOOTNOTE_BACKLINK_RE = re.compile(r"\[\u2191\]\(#footnote-ref-(\d+)\)")


def disambiguate_title_chapeau(remainder: str) -> Tuple[str, Optional[str]]:
    """Tach 'Tieu de Dieu + chapeau dinh kem' (Edge B).

    Dieu 3: 'Giai thich tu ngu Trong Bo luat nay, ... duoc hieu nhu sau:'
    -> ('Giai thich tu ngu', 'Trong Bo luat nay, ... nhu sau:')
    """
    low = remainder.lower()
    for trig in CHAPEAU_TRIGGERS:
        pos = low.find(trig)
        if pos == -1:
            continue
        # Tim bat dau cau chua trigger: dau cau gan nhat (. / : / dau dong)
        prefix = remainder[:pos].rstrip()
        starts = [m.end() for m in re.finditer(r"[.:]\s+", prefix)]
        # Cau dan thuong bat dau bang chu HOA: tim tu viet hoa cuoi cung
        words = re.split(r"\s+", prefix)
        cut = 0
        for k in range(len(words) - 1, -1, -1):
            if words[k] and words[k][0].isupper():
                cut = k
                break
        title = " ".join(words[:cut]).strip(" .:")
        chapeau = " ".join(words[cut:]).strip() + " " + remainder[pos:].strip()
        chapeau = re.sub(r"\s+", " ", chapeau).strip()
        if title and chapeau and len(chapeau) > 10:
            return title, chapeau
    return remainder.strip(), None


@dataclass
class ParsedPoint:
    letter: str
    body: str
    footnote_ids: List[int] = field(default_factory=list)
    occurrence: int = 1  # lan xuat hien thu may cua chu cai trong cung khoan


@dataclass
class ParsedClause:
    number: int
    implicit: bool = False
    lead: str = ""
    points: List[ParsedPoint] = field(default_factory=list)
    footnote_ids: List[int] = field(default_factory=list)

    @property
    def text_with_points(self) -> str:
        parts = []
        if self.lead.strip():
            parts.append(self.lead.strip())
        for p in self.points:
            parts.append(f"{p.letter}) {p.body}".strip())
        return "\n".join(parts)


@dataclass
class ParsedArticle:
    chapeau: Optional[str] = None
    clauses: List[ParsedClause] = field(default_factory=list)
    preamble_points: List[ParsedPoint] = field(default_factory=list)  # hiem
    footnote_ids: List[int] = field(default_factory=list)
    has_formula_image: bool = False
    parse_flags: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        parts = []
        if self.chapeau:
            parts.append(self.chapeau)
        for c in self.clauses:
            head = f"{c.number}. {c.lead}".strip() if c.lead else f"{c.number}."
            parts.append(head)
            for p in c.points:
                parts.append(f"{p.letter}) {p.body}".strip())
        return "\n".join(parts)


def _strip_md_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Footnote anchor trong title (VD Chuong XVII '...THI HANH [[6]]'):
    # xoa han de tranh du '6' trong title (P-029 footnote fix).
    text = re.sub(r"\s*\[\[.*?\]\]\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_points(lines: List[str]) -> Tuple[str, List[ParsedPoint], List[int]]:
    """Tach lead + points trong 1 doan (khoan hoac doan ngam)."""
    lead_parts: List[str] = []
    points: List[ParsedPoint] = []
    foot_ids: List[int] = []
    cur: Optional[ParsedPoint] = None
    for ln in lines:
        if not ln.strip():
            continue
        m = POINT_RE.match(ln)
        if m:
            # Lay ids tu FULL line truoc khi regex nuot anchor dinh kem
            _, line_ids = split_merged_footnote(ln)
            body = m.group(2).strip()
            body, ids = split_merged_footnote(body)
            ids = sorted(set(list(line_ids) + ids))
            foot_ids.extend(ids)
            cur = ParsedPoint(letter=m.group(1).lower(), body=body,
                              footnote_ids=ids)
            points.append(cur)
        elif cur is not None and (ln.startswith(" ") or ln.startswith("\t")):
            # Dong tiep cua diem (wrap)
            cur.body += " " + ln.strip()
        else:
            if cur is None:
                lead_parts.append(ln.strip())
            else:
                # Doan van sau diem ma khong phai diem moi -> gop vao lead phu
                lead_parts.append(ln.strip())
    return " ".join(lead_parts).strip(), points, sorted(set(foot_ids))


def parse_article_content(raw_body: str,
                          heading_chapeau: Optional[str] = None
                          ) -> ParsedArticle:
    """Boc tach chapeau/khoan/diem trong than 1 Dieu (ke ca 'Khoan 1 ngam')."""
    lines = [l.rstrip() for l in raw_body.splitlines()]
    # Nhom dong theo marker khoan:
    # - Marker explicit DAU TIEN (bat ky so nao) luon duoc chap nhan.
    # - Sau do: so TANG don dieu (n > prev) = khoan moi that (ke ca nhay coc
    #   do khoan bi bai bo khi hop nhat, VD D7: 1->3, D61: 2->4) + gan co GAP.
    # - So LAP/GIAM (n <= prev, VD noi dung trich dan luat khac danh so '1.'
    #   rieng trong Dieu 219) duoc gop vao khoan hien tai + gan co de audit.
    segments: List[Tuple[Optional[int], List[str]]] = []  # (clause_no|None, lines)
    cur_no: Optional[int] = None
    cur_lines: List[str] = []
    out_of_seq = False
    clause_gaps: List[str] = []

    def _has_explicit() -> bool:
        if cur_no is not None:
            return True
        return any(s[0] is not None for s in segments)

    for ln in lines:
        m = CLAUSE_RE.match(ln)
        # Dong 'N. ...' ngan co the la tieu de phu? Mac dinh: marker khoan
        # nhung loai tru truong hop footnote dinh nghia lan ('2. 2 Diem nay...')
        # -> xu ly o tang detach; o day giu nguyen logic don gian
        if m and len(ln.strip()) > 3:
            n = int(m.group(1))
            if not _has_explicit():
                accept = True
            elif cur_no is not None and n > cur_no:
                accept = True
                if n > cur_no + 1:
                    clause_gaps.append(f"CLAUSE_NUMBER_GAP:{cur_no}->{n}")
            else:
                accept = False
            if accept:
                if cur_lines or cur_no is not None or segments:
                    segments.append((cur_no, cur_lines))
                cur_no = n
                cur_lines = [m.group(2).strip()]
                continue
            out_of_seq = True
        cur_lines.append(ln)
    segments.append((cur_no, cur_lines))

    parsed = ParsedArticle()
    if has_formula_placeholder(raw_body):
        parsed.has_formula_image = True

    # Doan dau (truoc khoan danh so dau tien)
    first_no, first_lines = segments[0]
    if first_no is None:
        pre_text = " ".join(l.strip() for l in first_lines if l.strip())
        # Co diem a),b)... truoc khi co '2.' -> Khoan 1 ngam (Edge E)
        lead, points, fids = _parse_points(first_lines)
        if points:
            parsed.clauses.append(ParsedClause(
                number=1, implicit=True, lead=lead, points=points,
                footnote_ids=fids))
            parsed.footnote_ids.extend(fids)
        elif pre_text:
            parsed.chapeau = (heading_chapeau + " " + pre_text).strip() \
                if heading_chapeau else pre_text
        elif heading_chapeau:
            parsed.chapeau = heading_chapeau
    else:
        if heading_chapeau:
            parsed.chapeau = heading_chapeau

    for no, seg_lines in segments:
        if no is None:
            continue
        lead, points, fids = _parse_points(seg_lines)
        # Tach anchor footnote khoi lead
        lead, lead_ids = split_merged_footnote(lead)
        fids = sorted(set(fids + lead_ids))
        parsed.clauses.append(ParsedClause(
            number=no, implicit=False, lead=lead, points=points,
            footnote_ids=fids))
        parsed.footnote_ids.extend(fids)

    parsed.footnote_ids = sorted(set(parsed.footnote_ids))
    if out_of_seq:
        parsed.parse_flags.append("OUT_OF_SEQUENCE_CLAUSE_NUMBER")
    parsed.parse_flags.extend(clause_gaps)
    # Chu cai Diem lap lai trong 1 khoan (trich dan nhieu van ban nhu D219):
    # giu letter goc + danh occurrence de chunk_id duy nhat
    for cl in parsed.clauses:
        seen: Dict[str, int] = {}
        for p in cl.points:
            seen[p.letter] = seen.get(p.letter, 0) + 1
            p.occurrence = seen[p.letter]
        if any(v > 1 for v in seen.values()):
            parsed.parse_flags.append(
                f"REPEATED_POINT_LETTER_C{cl.number}")
    # Khoan danh so dau tien != 1 ma khong co doan mo dau -> thieu
    first_explicit = [c.number for c in parsed.clauses if not c.implicit]
    if first_explicit and first_explicit[0] != 1 and not parsed.chapeau \
            and not any(c.implicit for c in parsed.clauses):
        parsed.parse_flags.append(f"FIRST_CLAUSE_IS_{first_explicit[0]}")
    return parsed


FOOTNOTE_DEF_RE = re.compile(
    r"^\s*(\d+)\.\s+\d*\s*(.*sửa đổi.*|.*bổ sung.*|.*hiệu lực.*)$",
    re.IGNORECASE,
)
LAW_NO_RE = re.compile(r"số\s+([0-9]+/[0-9]{4}/[A-ZĐ0-9\-]+)")
EFF_DATE_RE = re.compile(
    r"có hiệu lực kể từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})"
)
REF_DETAIL_RE = re.compile(
    r"(điểm [a-zđ]\d* khoản \d+ Điều \d+[a-z]?|khoản \d+ Điều \d+[a-z]?|Điều \d+[a-z]?)",
    re.IGNORECASE,
)


def parse_footnote_defs(tail_text: str) -> Dict[int, Dict]:
    """Parse khoi dinh nghia footnote -> {n: {text, law_no, effective_date, ref_detail}}."""
    out: Dict[int, Dict] = {}
    lines = tail_text.splitlines()
    i = 0
    buf: List[str] = []
    cur: Optional[int] = None

    def flush():
        if cur is not None:
            text = " ".join(buf).strip()
            text = re.sub(r"\s*\[\u2191\]\(#footnote-ref-\d+\)", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            law = LAW_NO_RE.search(text)
            eff = EFF_DATE_RE.search(text)
            ref = REF_DETAIL_RE.search(text)
            out[cur] = {
                "text": text[:2000],
                "law_no": law.group(1) if law else None,
                "effective_date": (f"{eff.group(3)}-{int(eff.group(2)):02d}-{int(eff.group(1)):02d}"
                                   if eff else None),
                "ref_detail": ref.group(1) if ref else None,
                "needs_manual_review": not bool(law and eff),
            }

    for ln in lines:
        m = re.match(r"^\s*(\d+)\.\s+\d*\s*\S", ln)
        if m and ("sửa đổi" in ln or "bổ sung" in ln or "hiệu lực" in ln
                  or "quy định như sau" in ln):
            flush()
            cur = int(m.group(1))
            buf = [re.sub(r"^\s*\d+\.\s+\d*\s*", "", ln)]
        elif cur is not None:
            buf.append(ln)
    flush()
    return out


def parse_document(cleaned_text: str, filename_stem: str) -> DocumentTree:
    """Parse full cleaned markdown -> DocumentTree."""
    if filename_stem not in DOC_ID_MAP:
        raise ValueError(f"Chua map document_id cho file: {filename_stem}")
    info = DOC_ID_MAP[filename_stem]
    tree = DocumentTree(document_id=info["document_id"],
                        document_type=info["document_type"],
                        document_form=info["document_form"],
                        doc_code=info["doc_code"])
    lines = cleaned_text.splitlines()

    tracker = ChapterTracker()
    cur_chap: Optional[ChapterNode] = None
    cur_sec: Optional[SectionNode] = None
    sec_seen: set[int] = set()
    pending_article: Optional[Tuple[int, str, List[str], List[int]]] = None
    # (number, title, body_lines, anchor_ids)

    def flush_article():
        nonlocal pending_article
        if pending_article is None or cur_chap is None:
            pending_article = None
            return
        num, title, body_lines, aids = pending_article
        node = ArticleNode(number=num, title=title,
                           raw_body="\n".join(body_lines).strip(),
                           footnote_ids=sorted(set(aids)))
        if cur_sec is not None:
            cur_sec.articles.append(node)
        else:
            cur_chap.articles.append(node)
        pending_article = None

    for ln in lines:
        m = CHAP_RE.match(ln)
        if m:
            flush_article()
            canon, flags = tracker.register(m.group(1))
            cur_chap = ChapterNode(raw=m.group(1).upper(),
                                   canonical=canon,
                                   title=_strip_md_inline(m.group(2)) or None,
                                   anomaly_flags=flags)
            tree.chapters.append(cur_chap)
            if flags:
                tree.anomaly_flags.extend(
                    f"CHUONG {m.group(1)}: {f}" for f in flags)
            cur_sec, sec_seen = None, set()
            continue
        m = SEC_RE.match(ln)
        if m and cur_chap is not None:
            flush_article()
            num = int(m.group(1))
            flags = detect_section_anomaly(sec_seen, num)
            sec_seen.add(num)
            cur_sec = SectionNode(number=num,
                                  title=_strip_md_inline(m.group(2)) or None)
            cur_chap.sections.append(cur_sec)
            if flags:
                tree.anomaly_flags.extend(
                    f"CHUONG {cur_chap.raw} MUC {num}: {f}" for f in flags)
            continue
        m = ART_RE.match(ln)
        if m and cur_chap is not None:
            flush_article()
            remainder = _strip_md_inline(m.group(2))
            title, emb_chapeau = disambiguate_title_chapeau(remainder)
            pending_article = (int(m.group(1)), title, [], [])
            if emb_chapeau:
                pending_article[2].append(f"[EMBEDDED_CHAPEAU]{emb_chapeau}")
            continue
        if pending_article is not None:
            if PHAN_RE.match(ln):
                continue
            body, ids = split_merged_footnote(ln)
            pending_article[2].append(body)
            pending_article[3].extend(ids)

    flush_article()

    # Tach duoi footnote khoi Dieu cuoi (VPQH table + dinh nghia)
    if tree.chapters:
        last_holder = None
        last_ch = tree.chapters[-1]
        if last_ch.sections and last_ch.sections[-1].articles:
            last_holder = last_ch.sections[-1].articles[-1]
        elif last_ch.articles:
            last_holder = last_ch.articles[-1]
        if last_holder is not None:
            body_lines = last_holder.raw_body.splitlines()
            cut = None
            for k, bl in enumerate(body_lines):
                if TAIL_TABLE_RE.search(bl):
                    cut = k
                    break
            if cut is not None:
                tail_text = "\n".join(body_lines[cut:])
                last_holder.raw_body = "\n".join(body_lines[:cut]).strip()
                tree.footnotes = parse_footnote_defs(tail_text)

    return tree


def load_cleaned(stem: str, base_dir: str = "data/cleaned_markdown") -> str:
    with open(f"{base_dir}/{stem}.md", encoding="utf-8") as f:
        return f.read()


def document_ids() -> List[str]:
    return list(DOC_ID_MAP)
