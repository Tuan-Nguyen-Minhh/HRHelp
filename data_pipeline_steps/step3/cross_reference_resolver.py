"""Cross-reference Rule Engine (plan 3.4).

Thu tu uu tien: EXPLICIT > LIST_EXPANSION > SCOPED_CHAPEAU > BOUNDARY_CHECK(LOW).
Rule 4 List Expansion (moi): chuoi liet ke 'Dieu A, Dieu B... va Dieu Z <qualifier>'
-> qualifier cuoi ap dung cho TOAN BO chuoi (va loi doc nham self-reference).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .schema import CrossReference

BLLD_ID = "18/VBHN-VPQH"
BLLD_ALIASES = ["bộ luật lao động", "blld"]

# Mention: [diem X khoan Y] Dieu Z
MENTION_RE = re.compile(
    r"(?:điểm\s+([a-zđ]\d*)\s+)?(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)([a-z]?)",
    re.IGNORECASE,
)
# Chuoi liet ke: Dieu A, Dieu B [, ...] va Dieu Z
LIST_RE = re.compile(
    r"Điều\s+\d+[a-z]?(?:\s*[,;]\s*Điều\s+\d+[a-z]?|\s+và\s+Điều\s+\d+[a-z]?)+",
    re.IGNORECASE,
)
QUALIFIER_RE = re.compile(
    r"của\s+(Bộ luật[^.,;]*?|Luật[^.,;]*?|Nghị định[^.,;]*?|"
    r"Pháp lệnh[^.,;]*?|Hiến pháp)(?=[.,;]|$)",
    re.IGNORECASE,
)
SELF_WORDS = re.compile(
    r"(Nghị định này|Điều này|Khoản này|Bộ luật này)", re.IGNORECASE
)
LAW_NO_RE = re.compile(r"số\s+([0-9]+/[0-9]{4}/[A-ZĐ0-9\-]+)")


def _resolve_named(qualifier: str) -> str:
    q = qualifier.strip()
    if any(a in q.lower() for a in BLLD_ALIASES):
        return BLLD_ID
    m = LAW_NO_RE.search(q)
    if m:
        return m.group(1)
    return q  # giu nguyen ten goi neu khong chuan hoa duoc


def _sentence_around(text: str, pos: int, width: int = 250) -> str:
    start = max(0, pos - width)
    end = min(len(text), pos + width)
    left = text[start:pos]
    right = text[pos:end]
    # cat theo dau cau gan nhat
    ls = max(left.rfind("."), left.rfind(";"), left.rfind(":"))
    rs = min([p for p in (right.find("."), right.find(";")) if p != -1]
             or [len(right)])
    return text[start + (ls + 1 if ls != -1 else 0):pos + rs]


@dataclass
class DocScope:
    document_id: str
    max_article: int
    # Dieu 1 co chapeau huong ve BLLD (VD ND145/ND283 Dieu 1)
    scoped_to_blld: bool = False


def resolve_cross_references(text: str, scope: DocScope,
                             header_len: int = 0
                             ) -> List[CrossReference]:
    refs: List[CrossReference] = []
    consumed: List[Tuple[int, int]] = []  # span da xu ly boi List Expansion

    def _consumed(s: int, e: int) -> bool:
        return any(a <= s and e <= b for a, b in consumed)

    def _in_header(s: int) -> bool:
        # Match nam trong header_context (VD '[DIEU 49: ...]') -> bo qua,
        # khong phai dan chieu that
        return s < header_len

    # ---- Rule 4 (chay DAU TIEN): List Expansion ----
    for lm in LIST_RE.finditer(text):
        if _in_header(lm.start()):
            continue
        tail = text[lm.end():lm.end() + 120]
        qm = re.match(r"\s*(của\s+[^.,;]+)", tail, re.IGNORECASE)
        qualifier = qm.group(1) if qm else None
        # Chi ap dung khi co qualifier tuong minh o cuoi chuoi
        if qualifier:
            target = _resolve_named(qualifier)
            for am in re.finditer(r"Điều\s+(\d+)([a-z]?)", lm.group(0),
                                  re.IGNORECASE):
                refs.append(CrossReference(
                    target_doc=target, article=int(am.group(1)),
                    confidence="HIGH", rule="LIST_EXPANSION"))
            consumed.append((lm.start(), lm.end()))

    # ---- Cac mention con lai ----
    for m in MENTION_RE.finditer(text):
        if _in_header(m.start()):
            continue
        if _consumed(m.start(), m.end()):
            continue
        point, clause, art, _suf = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        sent = _sentence_around(text, m.start())

        # Rule 1: Explicit (qualifier trong cung cau)
        qm = QUALIFIER_RE.search(sent)
        if qm and not SELF_WORDS.search(qm.group(0)):
            refs.append(CrossReference(
                target_doc=_resolve_named(qm.group(1)), article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="HIGH", rule="EXPLICIT"))
            continue
        if SELF_WORDS.search(sent):
            refs.append(CrossReference(
                target_doc=scope.document_id, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="HIGH", rule="EXPLICIT_SELF"))
            continue

        # Rule 2 (truoc Boundary): Scoped Chapeau (Dieu 1 -> BLLD)
        if scope.scoped_to_blld and scope.document_id != BLLD_ID:
            refs.append(CrossReference(
                target_doc=BLLD_ID, article=art,
                clause=int(clause) if clause else None,
                point=point.lower() if point else None,
                confidence="HIGH", rule="SCOPED_CHAPEAU"))
            continue

        # Rule 3 cuoi: Boundary Check (suy luan yeu -> LOW)
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

    # Loai trung (giu thu tu)
    seen, uniq = set(), []
    for r in refs:
        key = (r.target_doc, r.article, r.clause, r.point, r.rule)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq
