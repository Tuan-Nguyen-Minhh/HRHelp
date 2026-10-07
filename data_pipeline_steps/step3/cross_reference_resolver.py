"""Cross-reference Rule Engine (plan 3.4) — FIXED 2026-09-27 (P-029).

Thu tu uu tien: EXPLICIT > LIST_EXPANSION > QUOTED_EXTERNAL > SCOPED_CHAPEAU > BOUNDARY_CHECK(LOW).
Fix P-029:
- target_doc greedy: dung capture tai boundary ':', newline, 'theo/khi/va/nhung/ma/;/,',
  safety net <=40 ky tu (ngoai tru KNOWN_LONG_LAWS).
- quoted external: doan trich dan nguyen van luat khac trong ngoac kep sau
  'sua doi, bo sung ... Luat/Bo luat <ten>' -> KHONG ap DEFAULT_SELF/EXPLICIT_SELF,
  tro dung ve van ban duoc trich dan (VD Dieu 219 BLLD -> Luat BHXH).
- confidence: target_doc dai >40 (tru allowlist) hoac chua '\n'/':' -> LOW.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .schema import CrossReference

BLLD_ID = "18/VBHN-VPQH"
BLLD_ALIASES = ["bộ luật lao động", "blld"]

MENTION_RE = re.compile(
    r"(?:điểm\s+([a-zđ]\d*)\s+)?(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)([a-z]?)",
    re.IGNORECASE,
)
LIST_RE = re.compile(
    r"Điều\s+\d+[a-z]?(?:\s*[,;]\s*Điều\s+\d+[a-z]?|\s+và\s+Điều\s+\d+[a-z]?)+",
    re.IGNORECASE,
)
# Capture THAM (greedy, KHONG lookahead punct) de giu luat co ','.
# _clean se cat gon tai boundary + allowlist. Khong dung lookahead vi cau dai
# khong co punct trong 80 ky tu se fail match (VD Dieu 65/Dieu 20).
# P-029 FIX 2026-10-01 (NQCT): them 'Noi quy' (tai lieu noi bo trich 'cua Noi quy...').
QUALIFIER_RE = re.compile(
    r"của\s+(Bộ luật[^\n:.;]{1,80}|Luật[^\n:.;]{1,80}|Nghị định[^\n:.;]{1,80}|"
    r"Pháp lệnh[^\n:.;]{1,80}|Hiến pháp|Nội quy[^\n:.;]{1,80})",
    re.IGNORECASE,
)
SELF_WORDS = re.compile(
    r"(Nghị định này|Điều này|Khoản này|Bộ luật này|Nội quy lao động này|Nội quy này)", re.IGNORECASE
)
# Qualifier self mo rong: 'cua Luat nay/Bo luat nay...' co the dung truoc text
# thuong (khong nhat thiet truoc dau cau) -> match rieng khong yeu cau punctuation.
SELF_QUAL_RE = re.compile(
    r"của\s+(Luật này|Bộ luật này|Nghị định này|Điều này|Khoản này|Nội quy lao động này|Nội quy này)\b",
    re.IGNORECASE,
)
# 'Luat nay' mo ho: trong quote external -> tro ve luat ngoai; ngoai quote -> self.
# QUAN TRONG: 'Bo luat nay' KHONG phai 'Luat nay' (tranh match nham substring).
# Dung helper _has_standalone_luat_nay() thay vi search truc tiep.
LUAT_NAY_RE = re.compile(r"Luật này", re.IGNORECASE)
BO_LUAT_NAY_RE = re.compile(r"Bộ luật này", re.IGNORECASE)
LAW_NO_RE = re.compile(r"số\s+([0-9]+/[0-9]{4}/[A-ZĐ0-9\-]+)")
# P-029 FIX 2026-10-01 (NQCT): so hieu luat TRAN (khong co 'so').
# VD 'Dieu 84 Nghi dinh 145/2020/ND-CP' -> '145/2020/ND-CP'.
# (LAW_NO_RE cu chi bat 'so 92/2015/QH13' theo TC9.)
BARE_LAW_NO_RE = re.compile(r"(\d{2,3}/20\d{2}/[A-ZĐ0-9\-]+)")
# P-029 FIX 2026-10-01 (NQCT): qualifier TRAN khong co 'cua', ke sat mention.
# VD 'Dieu 84 Nghi dinh 145/2020/ND-CP.' / 'Dieu 29 Bo luat Lao dong.'
# Chi match khi KE SAT sau mention (anchor ^ tren window) de tranh nhan nham
# luat cua Dieu khac cach xa trong cung cau dai. Loai tru '... nay' de
# nhuong cho logic self/ambiguous phia duoi.
BARE_QUALIFIER_RE = re.compile(
    r"^\s*(Nghị định\s+\d{2,3}/20\d{2}/[A-ZĐ0-9\-]+|Bộ luật Lao động\b|"
    r"Luật\s+(?!này\b)[^\n:.;]{1,60}|Bộ luật\s+(?!này\b)[^\n:.;]{1,60}|"
    r"Nghị định\s+(?!này\b)[^\n:.;]{1,60})",
    re.IGNORECASE,
)
# Self TRAN ke sat mention (khong co 'cua'): 'Dieu 15 Noi quy nay' -> self.
BARE_SELF_RE = re.compile(
    r"^\s*(Nội quy lao động này|Nội quy này|Nghị định này|Bộ luật này|Điều này|Khoản này)\b",
    re.IGNORECASE,
)


def _has_standalone_luat_nay(text: str) -> bool:
    """True neu co 'Luat nay' doc lap, KHONG phai phan cua 'Bo luat nay'."""
    if not LUAT_NAY_RE.search(text):
        return False
    # Loai tru moi match nam trong 'Bo luat nay'
    for m in LUAT_NAY_RE.finditer(text):
        start = max(0, m.start() - 4)
        prefix = text[start:m.start()].lower()
        if prefix.endswith("bộ ") or prefix.endswith("bo "):
            continue
        # Con lai la standalone ('cua Luat nay', 'Dieu nay cua Luat nay'...)
        return True
    return False


def _raw_is_bo_luat_nay(raw_q: str) -> bool:
    return bool(BO_LUAT_NAY_RE.search(raw_q))


def _raw_is_standalone_luat_nay(raw_q: str) -> bool:
    return _has_standalone_luat_nay(raw_q)

# Ten luat dai hop le vuot 40 ky tu (ngoai le duy nhat cua safety net).
KNOWN_LONG_LAWS = [
    "Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng",
]
KNOWN_LAW_PREFIXES = [
    "Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng",
    "Luật An toàn, vệ sinh lao động",
    "Bộ luật Lao động",
    "Luật Bảo hiểm xã hội",
    "Luật Xử lý vi phạm hành chính",
    "Luật Việc làm",
    "Luật Giáo dục nghề nghiệp",
    "Luật Giáo dục",
    "Luật Nghĩa vụ quân sự",
    "Luật Sĩ quan Quân đội nhân dân Việt Nam",
    "Luật Công an nhân dân",
    "Luật Cơ yếu",
    "Bộ luật Tố tụng dân sự",
    "Bộ luật Tố tụng hình sự",
    "Luật Bảo hiểm y tế",
    "Luật Công đoàn",
    "Nghị định này",
    "Bộ luật này",
]
# Ten chung chung bi cat cut (do window truncate) -> coi la invalid -> LOW.
GENERIC_TRUNCATED = {"bộ luật", "luật", "nghị định", "pháp lệnh", "hiến pháp"}

BOUNDARY_WORDS_RE = re.compile(
    r"\s+(theo|khi|và|nhưng|mà|trong|với|để|không|chưa|đã|kể|có|cho|đối với)\b",
    re.IGNORECASE,
)


def _clean_law_name(raw: str) -> str:
    """Cat target_doc tai boundary ro rang, tra ve ten gon."""
    q = (raw or "").strip()
    # Bo tien to 'cua'
    q = re.sub(r"^của\s+", "", q, flags=re.IGNORECASE).strip()
    # Bo artifact truncate envelope '[…]' / '…' / quotes
    q = q.replace("[…]", "").replace("…", "")
    q = q.replace("“", "").replace("”", "").replace('"', "").replace("'", "")
    q = re.sub(r"\s+", " ", q).strip()
    # Cat tai ':' va newline dau tien
    q = re.split(r"[:\n]", q, maxsplit=1)[0].strip()
    # Known prefix match TRUOC khi cat ','/';' (giu 'Luat An toan, ve sinh lao dong').
    for prefix in KNOWN_LAW_PREFIXES:
        if q.lower().startswith(prefix.lower()):
            return prefix
    # Cat tai ';' ',' dau tien (ten luat thuong khong chua, tru allowlist tren)
    q = re.split(r"[;,]", q, maxsplit=1)[0].strip()
    # Cat tai tu noi dau tien (theo/khi/va/nhung/ma/...)
    m = BOUNDARY_WORDS_RE.search(q)
    if m:
        q = q[:m.start()].strip()
    # Cat tai '.' du thua (VD 'Luat ... quy dinh.')
    q = q.split(".")[0].strip()
    q = re.sub(r"\s+", " ", q).strip(" .;:,")
    return q


def _is_valid_target(doc: str) -> bool:
    if "\n" in doc or ":" in doc:
        return False
    if doc in KNOWN_LONG_LAWS:
        return True
    if not doc:
        return False
    if doc.lower() in GENERIC_TRUNCATED:
        return False
    if len(doc) > 40:
        return False
    return True


def _nearest_qualifier_after(body: str, mention_end_body: int,
                             max_dist: int = 100
                             ) -> Optional[re.Match]:
    """Tim qualifier GAN NHAT ngay sau mention (VD 'Dieu 2 cua Luat X').

    Uu tien window hep 100 ky tu sau mention de tranh nhan nham qualifier
    cua Dieu khac trong cung cau dai (VD Dieu 2 nhan nham 'cua Bo luat Lao dong'
    cua Dieu 169 cach 200 ky tu). Tra ve match dau tien trong window.
    Neu co mention 'Dieu Y' khac chen giua mention hien tai va qualifier thi
    qualifier thuoc ve mention sau -> bo qua (tra None) de tranh nhan nham
    (VD 'Sua doi Dieu 54 nhu sau: ... Dieu 169 cua Bo luat...' -> Dieu 54
    khong duoc nhan 'cua Bo luat' cua Dieu 169).
    """
    window = body[mention_end_body:mention_end_body + max_dist]
    # P-029 FIX 2026-10-01 (NQCT): bare ke sat (khong 'cua') uu tien nhat.
    # VD 'Dieu 84 Nghi dinh 145/2020/ND-CP' / 'Dieu 29 Bo luat Lao dong'.
    # Anchor ^ tren window de khong nuot luat cua Dieu khac o xa.
    m_bare_self = BARE_SELF_RE.match(window)
    m_bare = BARE_QUALIFIER_RE.match(window)
    # Self truoc (khong yeu cau punctuation): 'cua Luat nay...'
    m_self = SELF_QUAL_RE.search(window)
    m_exp = QUALIFIER_RE.search(window)
    cands = []
    if m_bare_self:
        cands.append((m_bare_self.start(), m_bare_self))
    if m_bare:
        cands.append((m_bare.start(), m_bare))
    if m_exp:
        cands.append((m_exp.start(), m_exp))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    best_start, best = cands[0]
    # Kiem tra mention chen giua: 'Dieu ...' xuat hien truoc qualifier?
    between = window[:best_start]
    if MENTION_RE.search(between):
        return None
    return best


def _resolve_named(qualifier: str) -> Tuple[str, bool]:
    """Tra ve (target_doc, is_truncated_greedy_flag)."""
    raw = qualifier.strip()
    # Uu tien so hieu luat trong RAW (VD 'Bo luat To tung dan su so 92/2015/QH13'
    # -> '92/2015/QH13', theo TC9). Tim truoc khi clean cat bo so hieu.
    # Ngoai tru BLLD (khong dung so hieu, dung ID 18/VBHN-VPQH).
    # P-029 FIX 2026-10-01: them so hieu TRAN ('Nghi dinh 145/2020/ND-CP').
    if not any(a in raw.lower() for a in BLLD_ALIASES):
        m_raw = LAW_NO_RE.search(raw)
        if m_raw:
            return m_raw.group(1), False
        m_bare = BARE_LAW_NO_RE.search(raw)
        if m_bare:
            return m_bare.group(1), False
    cleaned = _clean_law_name(raw)
    if any(a in cleaned.lower() for a in BLLD_ALIASES):
        return BLLD_ID, False
    m = LAW_NO_RE.search(cleaned)
    if m:
        return m.group(1), False
    m2 = BARE_LAW_NO_RE.search(cleaned)
    if m2:
        return m2.group(1), False
    # 'Nghi dinh nay' -> se duoc caller map ve self; giu nguyen de nhan dien
    return cleaned, (not _is_valid_target(cleaned))


def _sentence_around(text: str, pos: int, width: int = 500) -> str:
    start = max(0, pos - width)
    end = min(len(text), pos + width)
    left = text[start:pos]
    right = text[pos:end]
    ls = max(left.rfind("."), left.rfind(";"), left.rfind(":"))
    rs = min([p for p in (right.find("."), right.find(";")) if p != -1]
             or [len(right)])
    return text[start + (ls + 1 if ls != -1 else 0):pos + rs]


def _detect_quoted_external(body: str) -> List[Tuple[int, int, str]]:
    """Tim span trich dan ngoai trong ngoac kep sau 'sua doi, bo sung ... Luat X'.

    Tra ve [(qstart, qend, external_law_name)].
    Dau hieu: cum 'Dieu X.' xuat hien trong '...' ngay sau cau
    'sua doi, bo sung ... Luat/Bo luat <ten>'.
    """
    spans: List[Tuple[int, int, str]] = []
    # Header sua doi: 'Sua doi, bo sung ... Luat/Bo luat <ten> ... :'
    hdr_pat = re.compile(
        r"sửa đổi,?\s*bổ sung[^“\"\n]{0,400}?(Bộ luật|Luật)\s+([^:;“\"\n]{1,80})",
        re.IGNORECASE,
    )
    for hm in hdr_pat.finditer(body):
        law_raw = (hm.group(1) + " " + hm.group(2)).strip()
        law_clean = _clean_law_name(law_raw)
        # Tim opening quote sau header (trong 300 ky tu ke tiep)
        search_from = hm.end()
        open_m = re.search(r"[“\"]", body[search_from:search_from + 400])
        if not open_m:
            continue
        qstart = search_from + open_m.start()
        # Closing quote: '”' hoac '"' tiep theo; neu khong co -> toi het chunk
        close_m = re.search(r"[”\"]", body[qstart + 1:])
        qend = qstart + 1 + close_m.end() if close_m else len(body)
        spans.append((qstart, qend, law_clean))
    # Fallback Dieu 219 BLLD: toan Dieu trich BHXH nhung chunk con khong con header.
    # Dau hieu: chunk thuoc Dieu 219 + chua 'bao hiem xa hoi'/'Luat nay' -> mac dinh BHXH.
    # (Xu ly o resolve via header_context; o day chi tra span tim duoc.)
    return spans


def _in_spans(pos: int, spans: List[Tuple[int, int, str]]) -> Optional[str]:
    for s, e, law in spans:
        if s <= pos <= e:
            return law
    return None


@dataclass
class DocScope:
    document_id: str
    max_article: int
    scoped_to_blld: bool = False


def resolve_cross_references(text: str, scope: DocScope,
                             header_len: int = 0
                             ) -> List[CrossReference]:
    refs: List[CrossReference] = []
    consumed: List[Tuple[int, int]] = []

    def _consumed(s: int, e: int) -> bool:
        return any(a <= s and e <= b for a, b in consumed)

    def _in_header(s: int) -> bool:
        return s < header_len

    body = text[header_len:] if header_len and header_len < len(text) else text
    # spans tinh tren body coordinates; mention pos body = m.start()-header_len
    quoted_spans_body = _detect_quoted_external(body)
    # Dieu 219 fallback: header chua DIEU 219 + body chua BHXH -> default external
    dieu219_quoted_default: Optional[str] = None
    if "ĐIỀU 219" in text.upper() and "bảo hiểm xã hội" in body.lower():
        dieu219_quoted_default = "Luật Bảo hiểm xã hội"

    # ---- Rule 4 (DAU TIEN): List Expansion ----
    for lm in LIST_RE.finditer(text):
        if _in_header(lm.start()):
            continue
        if _consumed(lm.start(), lm.end()):
            pass
        tail = text[lm.end():lm.end() + 150]
        # Cat tail tai boundary, khong nuot ca cau (cho phep ',' cho luat
        # 'An toan, ve sinh lao dong').
        tail_cut = re.split(r"[\n:;]", tail, maxsplit=1)[0]
        qm = re.match(r"\s*(của\s+[^\n:.;]{1,80})", tail_cut, re.IGNORECASE)
        qualifier = qm.group(1) if qm else None
        if qualifier is None:
            # P-029 FIX 2026-10-01: list co the trich tran ('Dieu 7 va Dieu 14
            # Bo luat Lao dong') — thu bare ke sat.
            bm = BARE_QUALIFIER_RE.match(tail_cut)
            if bm:
                qualifier = bm.group(1) if bm.lastindex else bm.group(0)
        if qualifier:
            # Neu qualifier la self-word ('Nghi dinh nay...') -> map ve self
            if SELF_WORDS.search(qualifier):
                target = scope.document_id
                conf = "HIGH"
            else:
                target, _flag = _resolve_named(qualifier)
                # 'Nghi dinh nay' sau clean van giu -> map self
                if target.lower() in ("nghị định này", "bộ luật này", "nội quy này"):
                    target = scope.document_id
                conf = "HIGH" if _is_valid_target(target) else "LOW"
            for am in re.finditer(r"Điều\s+(\d+)([a-z]?)", lm.group(0),
                                  re.IGNORECASE):
                refs.append(CrossReference(
                    target_doc=target, article=int(am.group(1)),
                    confidence=conf, rule="LIST_EXPANSION"))
            consumed.append((lm.start(), lm.end()))

    # ---- Cac mention con lai ----
    for m in MENTION_RE.finditer(text):
        if _in_header(m.start()):
            continue
        if _consumed(m.start(), m.end()):
            continue
        point, clause, art = m.group(1), m.group(2), int(m.group(3))
        # Sentence chi trong BODY (tranh nhiem header truncate '[…]').
        body_pos = m.start() - header_len if header_len else m.start()
        body_pos = max(body_pos, 0)
        mention_end_body = body_pos + len(m.group(0))
        sent = _sentence_around(body, body_pos)
        quoted_law = _in_spans(body_pos, quoted_spans_body)
        # Fallback Dieu219: continuation quote khong con header/opening quote.
        if quoted_law is None and dieu219_quoted_default:
            near_tmp = _nearest_qualifier_after(body, mention_end_body, 120)
            has_blld_near = bool(near_tmp and any(
                a in near_tmp.group(0).lower() for a in BLLD_ALIASES))
            if not has_blld_near and (
                    _has_standalone_luat_nay(sent)
                    or "bảo hiểm xã hội" in sent.lower()
                    or "bảo hiểm xã hội" in body.lower()):
                quoted_law = dieu219_quoted_default

        # Rule 1 UU TIEN: qualifier GAN NHAT ngay sau mention (<=120 ky tu).
        # Tranh nhan nham qualifier cua Dieu khac cach 200+ ky tu trong cung
        # cau dai (VD Dieu 2 nhan nham 'cua Bo luat Lao dong' cua Dieu 169).
        near_qm = _nearest_qualifier_after(body, mention_end_body, 120)
        if near_qm is not None:
            raw_q = near_qm.group(0)
            # UU TIEN explicit law cu the (BLLD/BHXH/...) truoc khi xet self-word
            # trong phan duoi trailing (VD 'cua Bo luat Lao dong va khoan 1 Dieu
            # nay...' chua ca BLLD lan 'Dieu nay' cua mention sau -> phai lay BLLD,
            # khong nhan nham EXPLICIT_SELF).
            target_pre, _ = _resolve_named(
                near_qm.group(1) if near_qm.lastindex else near_qm.group(0))
            is_specific_law = (
                target_pre == BLLD_ID
                or target_pre in KNOWN_LONG_LAWS
                or bool(LAW_NO_RE.search(target_pre))
                or bool(BARE_LAW_NO_RE.search(target_pre))
                or (target_pre in KNOWN_LAW_PREFIXES
                    and "này" not in target_pre.lower())
            )
            # Chi coi la self khi target khong phai law cu the
            # (P-029 FIX 2026-10-01: BARE_SELF_RE de bat 'Noi quy nay' ke sat,
            # SELF_WORDS da bao gom 'Noi quy nay').
            if (SELF_QUAL_RE.search(raw_q) or SELF_WORDS.search(raw_q)
                    or BARE_SELF_RE.search(raw_q)) \
                    and not is_specific_law:
                # 'Bo luat nay' -> self ro rang; 'Luat nay' doc lap moi mo ho.
                if _raw_is_standalone_luat_nay(raw_q) \
                        and not _raw_is_bo_luat_nay(raw_q):
                    if quoted_law or dieu219_quoted_default:
                        refs.append(CrossReference(
                            target_doc=quoted_law or dieu219_quoted_default,
                            article=art,
                            clause=int(clause) if clause else None,
                            point=point.lower() if point else None,
                            confidence="HIGH", rule="QUOTED_EXTERNAL"))
                    else:
                        refs.append(CrossReference(
                            target_doc=scope.document_id, article=art,
                            clause=int(clause) if clause else None,
                            point=point.lower() if point else None,
                            confidence="LOW", rule="AMBIGUOUS_LUAT_NAY"))
                elif quoted_law:
                    refs.append(CrossReference(
                        target_doc=quoted_law, article=art,
                        clause=int(clause) if clause else None,
                        point=point.lower() if point else None,
                        confidence="HIGH", rule="QUOTED_EXTERNAL"))
                else:
                    refs.append(CrossReference(
                        target_doc=scope.document_id, article=art,
                        clause=int(clause) if clause else None,
                        point=point.lower() if point else None,
                        confidence="HIGH", rule="EXPLICIT_SELF"))
                continue
            target, _ = _resolve_named(
                near_qm.group(1) if near_qm.lastindex else near_qm.group(0))
            if target.lower() in ("nghị định này", "bộ luật này", "nội quy này", "nội quy lao động này"):
                target = scope.document_id
            conf = "HIGH" if _is_valid_target(target) else "LOW"
            rule = "EXPLICIT" if conf == "HIGH" else "EXPLICIT_LOW"
            refs.append(CrossReference(
                target_doc=target, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence=conf, rule=rule))
            continue

        # Khong co qualifier ke sau -> xu ly 'Luat nay'/self/quoted/bare.
        if _has_standalone_luat_nay(sent):
            # Chi nhan 'Luat nay' gan mention (<=120 ky tu) de tranh nhiem xa.
            near_window = body[max(0, body_pos - 60):mention_end_body + 80]
            if _has_standalone_luat_nay(near_window):
                if quoted_law or dieu219_quoted_default:
                    refs.append(CrossReference(
                        target_doc=quoted_law or dieu219_quoted_default,
                        article=art,
                        clause=int(clause) if clause else None,
                        point=point.lower() if point else None,
                        confidence="HIGH", rule="QUOTED_EXTERNAL"))
                else:
                    refs.append(CrossReference(
                        target_doc=scope.document_id, article=art,
                        clause=int(clause) if clause else None,
                        point=point.lower() if point else None,
                        confidence="LOW", rule="AMBIGUOUS_LUAT_NAY"))
                continue
        if SELF_WORDS.search(sent):
            near_window = body[max(0, body_pos - 60):mention_end_body + 80]
            if SELF_WORDS.search(near_window):
                if quoted_law:
                    refs.append(CrossReference(
                        target_doc=quoted_law, article=art,
                        clause=int(clause) if clause else None,
                        point=point.lower() if point else None,
                        confidence="HIGH", rule="QUOTED_EXTERNAL"))
                else:
                    refs.append(CrossReference(
                        target_doc=scope.document_id, article=art,
                        clause=int(clause) if clause else None,
                        point=point.lower() if point else None,
                        confidence="HIGH", rule="EXPLICIT_SELF"))
                continue

        # Trong quote external nhung khong co qualifier: mac dinh ve luat ngoai
        if quoted_law:
            refs.append(CrossReference(
                target_doc=quoted_law, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="HIGH", rule="QUOTED_EXTERNAL"))
            continue

        # Rule 2: Scoped Chapeau (Dieu 1 -> BLLD)
        if scope.scoped_to_blld and scope.document_id != BLLD_ID:
            refs.append(CrossReference(
                target_doc=BLLD_ID, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="HIGH", rule="SCOPED_CHAPEAU"))
            continue

        # Rule 3 cuoi: Boundary Check (LOW) / Default Self (HIGH)
        if art > scope.max_article and scope.document_id != BLLD_ID:
            refs.append(CrossReference(
                target_doc=BLLD_ID, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="LOW", rule="BOUNDARY_CHECK"))
        else:
            refs.append(CrossReference(
                target_doc=scope.document_id, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="HIGH", rule="DEFAULT_SELF"))

    seen, uniq = set(), []
    for r in refs:
        key = (r.target_doc, r.article, r.clause, r.point, r.rule)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq
