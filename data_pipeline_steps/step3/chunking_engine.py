"""Chunking Engine (plan 3.3): Dieu -> Khoan -> Diem theo nguong token BGE-M3.

- Nguong chot (plan Q4): MAX_CHUNK_TOKENS=500, MIN_CHUNK_TOKENS=80.
- Chapeau ke thua xuong tan cap Diem (Clause Context Envelope).
- Atomic Penalty Unit: mac dinh cho moi chunk cap Diem/Khoan xu phat.
- token_count that bang tokenizer BGE-M3 (fallback uoc luong co danh dau).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .schema import (
    Chunk, ChunkMetadata, DocumentTree,
    ChapterNode, SectionNode, ArticleNode, build_chunk_id,
)
from .hierarchy_parser import (
    parse_article_content, ParsedArticle, ParsedClause, ParsedPoint,
)

MAX_CHUNK_TOKENS = 1000
MIN_CHUNK_TOKENS = 80
# DECISION 2026-09-26 (P-029): chot mistral-embed + tokenizer Mistral
# (mistral-common, offline) + nguong 1000 tokens (~300 tu tieng Viet).
# So lieu do that: Mistral 2.7-3.5 token/tu (BGE-M3 1.2-1.3x) nen 1000 tuong
# duong BGE-M3@500. Embed endpoint: mistral-embed (1024-dim, input toi da 8k).
# Backend tokenizer chon qua env STEP3_TOKENIZER hoac --tokenizer:
# 'mistral' (mac dinh) | 'bge' (BGE-M3, so lieu cu de doi chieu).
TOKENIZER_BACKEND = "mistral"

_tokenizer = None
_tokenizer_real = False
_tokenizer_kind = ""


def _load_bge():
    from tokenizers import Tokenizer
    local = Path(__file__).resolve().parent / "bge_m3_tokenizer.json"
    if local.exists():
        return Tokenizer.from_file(str(local))
    return Tokenizer.from_pretrained("BAAI/bge-m3")


def _load_mistral():
    # Tokenizer Mistral that cho mistral-embed: MistralTokenizer.v3
    # (v3/v7 cho count DONG NHAT tren sample luat 19/129/86 token).
    # API encode tho: instruct_tokenizer.tokenizer.encode(s, bos, eos).
    from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
    return MistralTokenizer.v3().instruct_tokenizer.tokenizer


def _encode_mistral(tok, text: str) -> int:
    return len(tok.encode(text, bos=False, eos=False))


def get_tokenizer(backend: str = ""):
    """Tokenizer that. Thu tu: cache -> tai (bge) / offline (mistral) -> fallback."""
    global _tokenizer, _tokenizer_real, _tokenizer_kind
    backend = backend or TOKENIZER_BACKEND
    if _tokenizer is not None and _tokenizer_kind == backend:
        return _tokenizer, _tokenizer_real
    try:
        if backend == "mistral":
            _tokenizer = _load_mistral()
        else:
            _tokenizer = _load_bge()
        _tokenizer_kind = backend
        _tokenizer_real = True
    except Exception:
        _tokenizer, _tokenizer_real = None, False
        _tokenizer_kind = ""
    return _tokenizer, _tokenizer_real


def count_tokens(text: str, backend: str = "") -> Tuple[int, bool]:
    """Tra ve (so_token, is_real_tokenizer)."""
    backend = backend or TOKENIZER_BACKEND
    tok, real = get_tokenizer(backend)
    if real and tok is not None:
        try:
            if backend == "mistral":
                return _encode_mistral(tok, text), True
            return len(tok.encode(text).ids), True
        except Exception:
            pass
    # Fallback khi khong tai duoc tokenizer: he so PHONG THU (overestimate)
    # theo backend de khong bao gio vuot nguong API (mistral-embed limit 8k).
    words = len(re.findall(r"\S+", text))
    ratio = 4.0 if backend == "mistral" else 1.5
    return int(words * ratio), False
# Budget hien thi cho envelope nguc canh (TOKEN, tu dong thich nghi backend).
# Metadata trich tu full text nen cat envelope khong mat du lieu.
ENVELOPE_TOKEN_BUDGET = 150
CHAPEAU_TOKEN_BUDGET = 60


MONEY_RE = re.compile(
    r"Phạt tiền từ\s+([\d.]+)\s*đồng\s+đến\s+([\d.]+)\s*đồng",
    re.IGNORECASE,
)
SUBJECT_RE = re.compile(
    r"đối với\s+(.+?)(?:\s+có một trong|\s+thực hiện|\s+khi\s+|:|;)",
    re.IGNORECASE,
)
TITLE_SUBJECT_RE = re.compile(
    r"vi phạm của\s+(.+?)(?:\s+có|\s+không|:|$)", re.IGNORECASE
)


def _parse_money(s: str) -> Optional[int]:
    try:
        return int(s.replace(".", ""))
    except ValueError:
        return None


def extract_penalty(lead: str, article_title: str = ""
                    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    m = MONEY_RE.search(lead or "")
    if not m:
        return None, None, None
    s = SUBJECT_RE.search(lead)
    subj = s.group(1).strip() if s else None
    if not subj and article_title:
        # Fallback: 'Vi pham cua <chu the>' trong tieu de Dieu
        t = TITLE_SUBJECT_RE.search(article_title)
        if t:
            subj = t.group(1).strip()
    return (_parse_money(m.group(1)), _parse_money(m.group(2)), subj)


def _truncate_to_tokens(text: str, budget: int, backend: str,
                        suffix: str = " […]") -> str:
    if count_tokens(text, backend)[0] <= budget:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi) // 2
        if count_tokens(text[:mid] + suffix, backend)[0] <= budget:
            lo = mid + 1
        else:
            hi = mid
    return text[:max(lo - 1, 0)].rstrip() + suffix


def _fit_envelope(article_header: str, art_chapeau: Optional[str],
                  clause_no: Optional[int], clause_lead: str,
                  backend: str = "") -> str:
    """Ghep envelope trong budget token: header + chapeau (cat) + lead (giu dau)."""
    prefix = article_header
    extra = ""
    if art_chapeau:
        ch = _truncate_to_tokens(art_chapeau.strip(), CHAPEAU_TOKEN_BUDGET,
                                 backend)
        extra += ("\n(Áp dụng theo quy định chung của Điều: "
                  f"\"{ch}\")")
    if clause_no is not None and clause_lead.strip():
        lead = " ".join(clause_lead.split())
        room = ENVELOPE_TOKEN_BUDGET - count_tokens(extra, backend)[0]
        if room < 30:
            room = 30
        lead = _truncate_to_tokens(lead, room, backend)
        extra += f"\n[Quy định tại Khoản {clause_no}: \"{lead}\"]"
    return prefix + extra


def build_header(doc_id: str, ch: ChapterNode, sec: Optional[SectionNode],
                 art: ArticleNode) -> str:
    parts = [f"[VĂN BẢN: {doc_id}]"]
    chap_label = f"[CHƯƠNG {ch.raw}: {ch.title or ''}]".strip()
    if ch.canonical != ch.raw:
        chap_label = (f"[CHƯƠNG {ch.raw} (mã hệ thống: {ch.canonical}): "
                      f"{ch.title or ''}]")
    parts.append(chap_label)
    if sec is not None:
        parts.append(f"[MỤC {sec.number}: {sec.title or ''}]")
    parts.append(f"[ĐIỀU {art.number}: {art.title}]")
    return " > ".join(parts)


def apply_formula_patch(cleaned_text: str, patch_path: str
                        ) -> Tuple[str, Dict[Tuple[int, int, int], dict]]:
    """Thay placeholder base64 bang marker cong thuc co dan image ref.

    Map theo thu tu xuat hien trong text <-> patch sap theo
    (article, clause, occurrence). Tra ve (text_moi, {(a,c,occ): entry}).
    """
    try:
        with open(patch_path, encoding="utf-8") as f:
            patch = json.load(f)
    except FileNotFoundError:
        return cleaned_text, {}
    entries = sorted(patch.get("patches", []),
                     key=lambda e: (e["article_number"], e["clause_number"],
                                    e.get("occurrence", 1)))
    ph_re = re.compile(r"!\[\]\(data:image/png;base64[^)]*\)")
    idx = 0

    def _repl(_m):
        nonlocal idx
        if idx < len(entries):
            e = entries[idx]
            idx += 1
            body = e.get("manual_text") or (
                f"[CÔNG THỨC CẦN NHẬP TAY — xem ảnh {e['image_file']}]")
            return body
        return "[CÔNG THỨC ẢNH — chưa map patch]"

    new_text = ph_re.sub(_repl, cleaned_text)
    used = {(e["article_number"], e["clause_number"], e.get("occurrence", 1)): e
            for e in entries[:idx]}
    return new_text, used


class ChunkingEngine:
    def __init__(self, max_tokens: int = MAX_CHUNK_TOKENS,
                 tokenizer: str = TOKENIZER_BACKEND):
        self.max_tokens = max_tokens
        global TOKENIZER_BACKEND
        TOKENIZER_BACKEND = tokenizer
        self.tokenizer = tokenizer
        self.tokenizer_fallback_used = False

    def _count(self, text: str) -> int:
        n, real = count_tokens(text, self.tokenizer)
        if not real:
            self.tokenizer_fallback_used = True
        return n

    def _footnote_status(self, tree: DocumentTree,
                         foot_ids: List[int]) -> Tuple[str, Optional[dict], List[str]]:
        flags: List[str] = []
        amended = None
        status = "ACTIVE"
        for fid in foot_ids:
            info = tree.footnotes.get(fid)
            if not info:
                status = "NEEDS_MANUAL_REVIEW"
                flags.append(f"FOOTNOTE_{fid}_DEF_MISSING")
            elif info.get("needs_manual_review") or not info.get("law_no"):
                status = "NEEDS_MANUAL_REVIEW"
                flags.append(f"FOOTNOTE_{fid}_NEEDS_REVIEW")
            else:
                status = "AMENDED"
                amended = {"law_no": info["law_no"],
                           "effective_date": info.get("effective_date"),
                           "ref_detail": info.get("ref_detail")}
        return status, amended, flags

    def chunk_document(self, tree: DocumentTree,
                       formula_hits: Optional[Dict[Tuple[int, int, int], dict]] = None
                       ) -> List[Chunk]:
        chunks: List[Chunk] = []
        for ch, sec, art in tree.all_articles():
            header = build_header(tree.document_id, ch, sec, art)
            # raw_body da duoc parser tach anchor; chapeau nhung tu heading
            emb_chapeau = None
            body = art.raw_body
            if body.startswith("[EMBEDDED_CHAPEAU]"):
                first, _, rest = body[len("[EMBEDDED_CHAPEAU]"):].partition("\n")
                emb_chapeau = first.strip()
                body = rest.strip()
            parsed = parse_article_content(body, heading_chapeau=emb_chapeau)
            # Chapeau rieng cua tung Dieu (de ke thua) + co parse lan xuong chunk
            art_chapeau = parsed.chapeau
            art_parse_flags = list(parsed.parse_flags)

            if not parsed.clauses:
                # Dieu khong chia khoan (VD Dieu 1 BLLD): 1 chunk ARTICLE
                chunks.append(self._make_chunk(
                    tree, ch, sec, art, header, level="ARTICLE",
                    clause_no=None, point=None,
                    chapeau_text=None, has_chapeau=False,
                    body_text=body, foot_ids=art.footnote_ids,
                    formula_hits=formula_hits, extra_flags=art_parse_flags))
                continue

            # Uoc tinh full Dieu
            full_text = parsed.full_text
            if self._count(header + "\n" + full_text) <= self.max_tokens:
                chunks.append(self._make_chunk(
                    tree, ch, sec, art, header, level="ARTICLE",
                    clause_no=None, point=None,
                    chapeau_text=art_chapeau, has_chapeau=bool(art_chapeau),
                    body_text=full_text, foot_ids=parsed.footnote_ids,
                    formula_hits=formula_hits, extra_flags=art_parse_flags))
                continue

            # Cat xuong Khoan (envelope vua budget)
            for cl in parsed.clauses:
                clause_prefix = _fit_envelope(header, art_chapeau, None, "",
                                             self.tokenizer)
                clause_text = cl.text_with_points
                if self._count(clause_prefix + "\n" + clause_text) <= self.max_tokens:
                    pmin, pmax, psubj = extract_penalty(cl.lead, art.title)
                    chunks.append(self._make_chunk(
                        tree, ch, sec, art, clause_prefix, level="CLAUSE",
                        clause_no=cl.number, point=None,
                        chapeau_text=art_chapeau, has_chapeau=bool(art_chapeau),
                        body_text=clause_text, foot_ids=cl.footnote_ids,
                        penalty=(pmin, pmax, psubj),
                        implicit_clause=cl.implicit,
                        formula_hits=formula_hits, extra_flags=art_parse_flags))
                    continue
                # Cat tiep xuong Diem (Atomic Penalty Unit: envelope bat buoc)
                point_prefix = _fit_envelope(header, art_chapeau,
                                             cl.number, cl.lead,
                                             self.tokenizer)
                for pt in cl.points:
                    pt_text = f"Điểm {pt.letter}) {pt.body}".strip()
                    pt_key = (pt.letter if pt.occurrence == 1
                              else f"{pt.letter}-{pt.occurrence}")
                    pmin, pmax, psubj = extract_penalty(cl.lead, art.title)
                    chunks.append(self._make_chunk(
                        tree, ch, sec, art, point_prefix, level="POINT",
                        clause_no=cl.number, point=pt_key,
                        chapeau_text=art_chapeau, has_chapeau=bool(art_chapeau),
                        body_text=pt_text, foot_ids=pt.footnote_ids,
                        penalty=(pmin, pmax, psubj),
                        implicit_clause=cl.implicit,
                        formula_hits=formula_hits, extra_flags=art_parse_flags))
        return chunks

    def _make_chunk(self, tree, ch, sec, art, header, level,
                    clause_no, point, chapeau_text, has_chapeau,
                    body_text, foot_ids, penalty=(None, None, None),
                    implicit_clause=False, formula_hits=None,
                    extra_flags=None) -> Chunk:
        cid = build_chunk_id(tree.doc_code, ch.canonical,
                             sec.number if sec else None,
                             art.number, clause_no, point)
        parent = None
        if level == "CLAUSE":
            parent = build_chunk_id(tree.doc_code, ch.canonical,
                                    sec.number if sec else None, art.number)
        elif level == "POINT":
            parent = build_chunk_id(tree.doc_code, ch.canonical,
                                    sec.number if sec else None,
                                    art.number, clause_no)
        status, amended, fflags = self._footnote_status(tree, foot_ids or [])
        flags: List[str] = []
        for f in ch.anomaly_flags:
            flags.append(f.split(":")[0])
        flags.extend(fflags)
        flags.extend(extra_flags or [])
        if "[CÔNG THỨC" in body_text:
            flags.append("MISSING_FORMULA_IMAGE")
        full = header + "\n" + body_text
        tok_n = self._count(full)
        if level == "POINT" and tok_n > self.max_tokens:
            # Diem don le vuot nguong: khong be cau (vo toan ven phap ly),
            # gan co de audit (BGE-M3 ctx 8k van embed duoc)
            flags.append("POINT_BODY_OVER_LIMIT")
        meta = ChunkMetadata(
            document_id=tree.document_id,
            document_type=tree.document_type,
            document_form=tree.document_form,
            chapter_raw=ch.raw, chapter_canonical=ch.canonical,
            chapter_title=ch.title,
            section_number=sec.number if sec else None,
            section_title=sec.title if sec else None,
            article_number=art.number, article_title=art.title,
            clause_number=clause_no,
            clause_number_is_implicit=implicit_clause if clause_no else False,
            point_letter=point, chunk_level=level,
            has_chapeau=has_chapeau, chapeau_text=chapeau_text,
            penalty_min_vnd=penalty[0], penalty_max_vnd=penalty[1],
            penalty_subject=penalty[2],
            effective_status=status, amended_by=amended,
            anomaly_flags=sorted(set(flags)),
            token_count=tok_n,
        )
        return Chunk(chunk_id=cid, parent_chunk_id=parent,
                     header_context=header, text=body_text, metadata=meta)
