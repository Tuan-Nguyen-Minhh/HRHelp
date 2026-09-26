"""Anomaly Detector tach rieng (plan 3.2): trung/nhay coc Chuong-Muc, footnote, cong thuc."""
from __future__ import annotations

import re
from typing import List, Tuple, Optional

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> Optional[int]:
    s = s.strip().upper()
    if not s or any(c not in ROMAN_VALUES for c in s):
        return None
    total, prev = 0, 0
    for c in reversed(s):
        v = ROMAN_VALUES[c]
        total = total - v if v < prev else total + v
        prev = v
    return total


def int_to_roman(n: int) -> str:
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
             (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
             (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, sym in table:
        while n >= v:
            out += sym
            n -= v
    return out


class ChapterTracker:
    """Theo doi so Chuong: phat hien trung + chuan hoa canonical + nhay coc."""

    def __init__(self):
        self.seen: dict[str, int] = {}
        self.flags: List[str] = []
        self.last_value: Optional[int] = None
        self.last_raw: Optional[str] = None

    def register(self, raw: str) -> Tuple[str, List[str]]:
        """Tra ve (canonical, flags) cho 1 so Chuong raw."""
        raw_u = raw.strip().upper()
        flags: List[str] = []
        if raw_u in self.seen:
            # Trung: de xuat canonical = so La Ma lon nhat da thay + 1
            max_seen = max(
                (roman_to_int(k) or 0) for k in self.seen
            )
            canon = int_to_roman(max_seen + 1)
            flags.append(
                f"DUPLICATE_CHAPTER_NUMBER:{raw_u}-> {canon}"
            )
            self.seen[raw_u] += 1
            self.last_value = roman_to_int(canon)
            self.last_raw = raw_u
            return canon, flags
        val = roman_to_int(raw_u)
        if val is not None and self.last_value is not None and val > self.last_value + 1:
            flags.append(
                f"CHAPTER_SEQUENCE_JUMP:{self.last_raw}->{raw_u}"
            )
        self.seen[raw_u] = 1
        self.last_value = val
        self.last_raw = raw_u
        return raw_u, flags


def detect_section_anomaly(seen: set[int], num: int) -> List[str]:
    flags: List[str] = []
    if num in seen:
        flags.append(f"DUPLICATE_SECTION_NUMBER:{num}")
    elif seen and num > max(seen) + 1:
        flags.append(f"SECTION_SEQUENCE_JUMP:{max(seen)}->{num}")
    return flags


FOOTNOTE_ANCHOR_RE = re.compile(r"\[\[(\d+)\]\]\(#footnote-(\d+)\)")
# So footnote le dan xen: a)2[[2]... / 3.3[[3]... / 8a.5[[5]...
MERGED_FOOTNOTE_RE = re.compile(
    r"^(\s*(?:\d+[a-z]?\.|[a-zđ]\)))(\d+)\s*(\[\[\d+\]\]\(#footnote-\d+\))"
)


def split_merged_footnote(text: str) -> Tuple[str, List[int]]:
    """Tach so footnote bi MarkItDown dan vao nhan Khoan/Diem.

    'a)2[[2]](#footnote-2)Thanh lap...' -> ('a)[[2]](#footnote-2)Thanh lap...', [2])
    Tra ve (text_da_tach, [footnote_ids]).
    """
    ids: List[int] = []
    for m in FOOTNOTE_ANCHOR_RE.finditer(text):
        ids.append(int(m.group(1)))
    cleaned = MERGED_FOOTNOTE_RE.sub(r"\1\3", text)
    return cleaned, sorted(set(ids))


def has_formula_placeholder(text: str) -> bool:
    return "data:image/png;base64" in text
