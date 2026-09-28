"""Query thử hybrid search từ CLI.

Usage:
    python scripts/query_legal.py --query "Tuổi nghỉ hưu là bao nhiêu?"
    python scripts/query_legal.py --query "..." --top-k 10 --mode vector
    python scripts/query_legal.py --interactive   # gõ nhiều câu liên tiếp
    python scripts/query_legal.py --query "..." --doc 18/VBHN-VPQH --article 169
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.hybrid_search import (  # noqa: E402
    SearchFilters,
    SearchMode,
    search,
)


def show(query: str, top_k: int, mode: SearchMode, filters: SearchFilters) -> None:
    hits = search(query, top_k=top_k, mode=mode, filters=filters)
    print(f"\nquery: {query}")
    print(f"mode={mode.value} top_k={top_k} -> {len(hits)} hits")
    print("-" * 100)
    for i, h in enumerate(hits, 1):
        print(f"[{i}] {h.citation} | score={h.score:.5f} "
              f"| vec_rank={h.vector_rank} bm25_rank={h.bm25_rank}")
        print(f"    {h.text[:220].replace(chr(10), ' ')}")
    print()


def main() -> int:
    p = argparse.ArgumentParser(description="Query thử hybrid search B7")
    p.add_argument("--query", "-q", default="")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--mode", choices=["hybrid", "vector", "bm25"], default="hybrid")
    p.add_argument("--doc", default=None, help="vd: 18/VBHN-VPQH")
    p.add_argument("--article", type=int, default=None)
    p.add_argument("--interactive", "-i", action="store_true")
    args = p.parse_args()

    mode = SearchMode(args.mode)
    filters = SearchFilters(document_id=args.doc, article_number=args.article)

    if args.interactive or not args.query:
        print("Gõ câu hỏi (tiếng Việt), Enter để tìm, 'quit' để thoát. "
              f"[mode={mode.value}, top_k={args.top_k}]")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            show(q, args.top_k, mode, filters)
        return 0

    show(args.query, args.top_k, mode, filters)
    return 0


if __name__ == "__main__":
    sys.exit(main())
