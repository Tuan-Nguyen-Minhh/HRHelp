"""Dieu phoi Buoc 3: cleaned_markdown -> document_tree.json -> chunks.json + refs.

Chay: python -m data_pipeline_steps.step3.run_step3 [--doc ND283_2026] [--out DIR]
Khong doi so: chay full 3 van ban.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .hierarchy_parser import (
    parse_document, load_cleaned, document_ids, DOC_ID_MAP,
)
from .chunking_engine import (
    ChunkingEngine, apply_formula_patch, MAX_CHUNK_TOKENS,
)
from .cross_reference_resolver import (
    resolve_cross_references, DocScope,
)

STEP3_DIR = Path(__file__).resolve().parent
OUT_DIR = STEP3_DIR / "output"


def _is_scoped_to_blld(chapeau: str | None, body_head: str) -> bool:
    probe = ((chapeau or "") + " " + (body_head or "")).lower()
    return "bộ luật lao động" in probe or "blld" in probe


def process_document(stem: str, out_dir: Path, engine: ChunkingEngine,
                     verbose: bool = True) -> dict:
    info = DOC_ID_MAP[stem]
    text = load_cleaned(stem)

    formula_hits = None
    if stem.startswith("nghi-dinh-145"):
        text, formula_hits = apply_formula_patch(
            text, str(STEP3_DIR / "formulas_patch.json"))

    tree = parse_document(text, stem)
    (out_dir / f"document_tree_{info['doc_code']}.json").write_text(
        json.dumps(tree.to_dict(), ensure_ascii=False, indent=1),
        encoding="utf-8")

    chunks = engine.chunk_document(tree, formula_hits=formula_hits)

    # Gan cross-reference cho tung chunk
    scoped_articles = set()
    for ch, sec, art in tree.all_articles():
        if art.number == 1:
            emb = ""
            body = art.raw_body
            if body.startswith("[EMBEDDED_CHAPEAU]"):
                emb, _, body = body[len("[EMBEDDED_CHAPEAU]"):].partition("\n")
            if _is_scoped_to_blld(emb or None, body[:600]):
                scoped_articles.add(art.number)

    for c in chunks:
        md = c.metadata
        scope = DocScope(document_id=tree.document_id,
                         max_article=info["max_article"],
                         scoped_to_blld=(md.article_number in scoped_articles))
        c.references = resolve_cross_references(
            c.header_context + "\n" + c.text, scope,
            header_len=len(c.header_context) + 1)

    payload = [c.to_dict() for c in chunks]
    (out_dir / f"chunks_{info['doc_code']}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    levels: dict[str, int] = {}
    over, flagged = 0, 0
    for c in chunks:
        levels[c.metadata.chunk_level] = levels.get(c.metadata.chunk_level, 0) + 1
        if c.metadata.token_count > engine.max_tokens:
            over += 1
        if c.metadata.anomaly_flags:
            flagged += 1
    stats = {
        "stem": stem, "document_id": tree.document_id,
        "tokenizer": engine.tokenizer,
        "max_tokens": engine.max_tokens,
        "articles_in_tree": tree.article_count(),
        "chunks": len(chunks), "levels": levels,
        "chunks_over_token_limit": over,
        "chunks_with_anomaly_flags": flagged,
        "tokenizer_fallback_used": engine.tokenizer_fallback_used,
        "tree_anomalies": tree.anomaly_flags,
    }
    if verbose:
        print(f"[{info['doc_code']}] articles={stats['articles_in_tree']} "
              f"chunks={len(chunks)} levels={levels} over={over} "
              f"flagged={flagged}")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=None,
                    help="Chi chay 1 stem (VD 283_2026_ND-CP_642116)")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--tokenizer", default="mistral", choices=["bge", "mistral"],
                    help="Backend dem token (mac dinh mistral theo DECISION 2026-09-26)")
    ap.add_argument("--max-tokens", type=int, default=MAX_CHUNK_TOKENS)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = ChunkingEngine(max_tokens=args.max_tokens,
                            tokenizer=args.tokenizer)
    stems = [args.doc] if args.doc else document_ids()
    all_stats = [process_document(s, out_dir, engine) for s in stems]
    (out_dir / "step3_stats.json").write_text(
        json.dumps(all_stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Tokenizer fallback used:", engine.tokenizer_fallback_used)


if __name__ == "__main__":
    sys.exit(main())
