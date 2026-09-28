"""Buoc 3: Data model chuan cho chunk phap ly (theo Phan B - semantic_chunking_plan.md)."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import json


@dataclass
class CrossReference:
    target_doc: str          # document_id dich, VD "18/VBHN-VPQH"
    article: int             # so Dieu dich
    clause: Optional[int] = None
    point: Optional[str] = None
    confidence: str = "HIGH"  # HIGH | LOW
    rule: str = ""           # EXPLICIT | LIST_EXPANSION | SCOPED_CHAPEAU | BOUNDARY_CHECK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChunkMetadata:
    document_id: str
    document_type: str        # BO_LUAT | NGHI_DINH | ...
    document_form: str        # VAN_BAN_GOC | VAN_BAN_HOP_NHAT
    chapter_raw: Optional[str] = None
    chapter_canonical: Optional[str] = None
    chapter_title: Optional[str] = None
    section_number: Optional[int] = None
    section_title: Optional[str] = None
    article_number: int = 0
    article_title: str = ""
    clause_number: Optional[int] = None
    clause_number_is_implicit: bool = False
    point_letter: Optional[str] = None
    chunk_level: str = "ARTICLE"  # ARTICLE | CLAUSE | POINT
    has_chapeau: bool = False
    chapeau_text: Optional[str] = None
    penalty_min_vnd: Optional[int] = None
    penalty_max_vnd: Optional[int] = None
    penalty_subject: Optional[str] = None
    effective_status: str = "ACTIVE"  # ACTIVE | AMENDED | NEEDS_MANUAL_REVIEW
    amended_by: Optional[Dict[str, Any]] = None
    anomaly_flags: List[str] = field(default_factory=list)
    token_count: int = 0
    # P-029 FIX (Dieu 219 BLLD): chunk nam trong doan trich dan nguyen van
    # luat khac trong ngoac kep -> True (tanh cay khoan/diem rieng, tranh
    # dung nham 'khoan N Dieu 219' khi thuc chat la khoan cua luat khac).
    is_quoted_external_text: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    chunk_id: str
    parent_chunk_id: Optional[str]
    header_context: str
    text: str
    metadata: ChunkMetadata
    references: List[CrossReference] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def build_chunk_id(doc_code: str, chapter_canon: Optional[str],
                   section_num: Optional[int], article_num: int,
                   clause_num: Optional[int] = None,
                   point_letter: Optional[str] = None) -> str:
    """Dinh danh phan cap RESTful-like: ND145_2020:C03:M01:A03:C01:P-a."""
    parts = [doc_code]
    parts.append(f"C{chapter_canon}" if chapter_canon else "C00")
    parts.append(f"M{section_num:02d}" if section_num else "M00")
    parts.append(f"A{article_num:03d}")
    if clause_num is not None:
        parts.append(f"C{clause_num:02d}")
    if point_letter is not None:
        parts.append(f"P-{point_letter}")
    return ":".join(parts)


# ---- Document tree (output trung gian cua Hierarchy Parser) ----

@dataclass
class ArticleNode:
    number: int
    title: str
    chapeau: Optional[str] = None
    raw_body: str = ""
    footnote_ids: List[int] = field(default_factory=list)


@dataclass
class SectionNode:
    number: int
    title: Optional[str] = None
    articles: List[ArticleNode] = field(default_factory=list)


@dataclass
class ChapterNode:
    raw: str
    canonical: str
    title: Optional[str] = None
    anomaly_flags: List[str] = field(default_factory=list)
    sections: List[SectionNode] = field(default_factory=list)
    articles: List[ArticleNode] = field(default_factory=list)  # Dieu thuoc truc tiep Chuong


@dataclass
class DocumentTree:
    document_id: str
    document_type: str
    document_form: str
    doc_code: str
    chapters: List[ChapterNode] = field(default_factory=list)
    footnotes: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    anomaly_flags: List[str] = field(default_factory=list)

    def all_articles(self):
        for ch in self.chapters:
            for a in ch.articles:
                yield ch, None, a
            for sec in ch.sections:
                for a in sec.articles:
                    yield ch, sec, a

    def article_count(self) -> int:
        return sum(1 for _ in self.all_articles())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
