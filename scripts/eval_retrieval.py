"""B7: run the golden retrieval set through vector-only, BM25-only and hybrid.

Plan: ``data_pipeline_steps/step6_7_plan.md`` section 3.7.

For every query in ``eval/legal_golden.json`` this script runs the three arms
and reports:

* **Hit@1**  — the first returned chunk is one of ``expected_chunk_ids``
* **Hit@5**  — any of the first five is one of ``expected_chunk_ids``
* **MRR**    — 1 / rank of the first expected chunk, 0 if it is not in the top 5
* **Article@5** — the query's ``must_contain_article`` appears in the top 5 of the
  *right document*. This is the weaker V5 bar: BM25 is weak on Vietnamese, so
  the plan only asks it to reach the right Điều, not the right chunk.

The acceptance floor (V6) lives in ``scripts/verify_embeddings.py``, not here —
this script measures and prints, it does not decide. Keeping the two separate
means the measurement can be re-run and inspected without anyone quietly editing
a threshold.

Results are written to ``eval/results/`` with a date-stamped filename so every
run is kept, mirroring the numbered ``verify_db_*.log`` history.

Usage:
    python scripts/eval_retrieval.py
    python scripts/eval_retrieval.py --top-k 5
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402
from src.services.embeddings_client import EmbeddingClient  # noqa: E402
from src.services.hybrid_search import (  # noqa: E402
    DEFAULT_TOP_K,
    SearchMode,
    embed_query,
    hybrid_search,
    search,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval_retrieval")

GOLDEN_PATH = PROJECT_ROOT / "eval" / "legal_golden.json"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"

MODES = (SearchMode.VECTOR, SearchMode.BM25, SearchMode.HYBRID)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def first_expected_rank(hits: list[str], expected: set[str], cutoff: int) -> int | None:
    for i, chunk_id in enumerate(hits[:cutoff], start=1):
        if chunk_id in expected:
            return i
    return None


def score_query(hits: list[Any], case: dict[str, Any], top_k: int) -> dict[str, Any]:
    ids = [h.chunk_id for h in hits]
    expected = set(case["expected_chunk_ids"])
    rank = first_expected_rank(ids, expected, top_k)
    doc = case.get("expected_document_id")
    art = case.get("must_contain_article")
    article_hit = (
        any(h.document_id == doc and h.article_number == art for h in hits[:top_k])
        if doc is not None and art is not None
        else None
    )
    return {
        "top_ids": ids,
        "top_articles": [f"{h.document_id}#D{h.article_number}" for h in hits],
        "hit_at_1": 1.0 if rank == 1 else 0.0,
        "hit_at_5": 1.0 if rank is not None else 0.0,
        "rr": (1.0 / rank) if rank else 0.0,
        "first_expected_rank": rank,
        "article_at_5": article_hit,
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_table(rows: list[dict[str, Any]], top_k: int) -> None:
    width = 78
    logger.info("=" * width)
    logger.info(f"PER-QUERY DETAIL (top_k={top_k})")
    logger.info("=" * width)
    for row in rows:
        logger.info(f"[{row['id']}] {row['query']}")
        logger.info(
            f"    expect: {row['expected_chunk_ids']} "
            f"(must_contain_article={row.get('must_contain_article')})"
        )
        for mode in MODES:
            s = row["results"][mode.value]
            mark = "HIT " if s["hit_at_5"] else "MISS"
            art = "-" if s["article_at_5"] is None else ("yes" if s["article_at_5"] else "no")
            logger.info(
                f"    {mode.value:<6} {mark} rank={s['first_expected_rank']} "
                f"article_at_5={art}"
            )
            logger.info(f"           {s['top_articles']}")
        logger.info("")


def print_summary(per_mode: dict[str, dict[str, float]], n: int) -> None:
    width = 78
    logger.info("=" * width)
    logger.info(f"SUMMARY over {n} queries")
    logger.info("=" * width)
    header = f"{'mode':<8}{'Hit@1':>10}{'Hit@5':>10}{'MRR':>10}{'Article@5':>12}"
    logger.info(header)
    logger.info("-" * len(header))
    for mode in MODES:
        m = per_mode[mode.value]
        logger.info(
            f"{mode.value:<8}{m['hit_at_1']:>10.3f}{m['hit_at_5']:>10.3f}"
            f"{m['mrr']:>10.3f}{m['article_at_5']:>12.3f}"
        )


def write_results(payload: dict[str, Any], stamp: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"retrieval_eval_{stamp}.json"
    md_path = RESULTS_DIR / f"retrieval_eval_{stamp}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    lines = [
        "# Retrieval eval — B7",
        "",
        f"- Run: `{payload['run_at']}`",
        f"- Model: `{settings.EMBEDDING_MODEL}` ({settings.EMBEDDING_DIMENSIONS}-dim)",
        f"- Golden set: `eval/legal_golden.json` v{payload['golden_version']} "
        f"({payload['n_queries']} queries, pinned {payload['golden_pinned_at']})",
        f"- top_k: {payload['top_k']}",
        "",
        "## Summary",
        "",
        "| mode | Hit@1 | Hit@5 | MRR | Article@5 |",
        "|---|---|---|---|---|",
    ]
    for mode in MODES:
        m = payload["summary"][mode.value]
        lines.append(
            f"| {mode.value} | {m['hit_at_1']:.3f} | {m['hit_at_5']:.3f} | "
            f"{m['mrr']:.3f} | {m['article_at_5']:.3f} |"
        )
    lines += ["", "## Per query", ""]
    for row in payload["queries"]:
        lines.append(f"### [{row['id']}] {row['query']}")
        lines.append("")
        lines.append(f"- expected: `{row['expected_chunk_ids']}`")
        lines.append(f"- must_contain_article: `{row.get('must_contain_article')}`")
        lines.append("")
        lines.append("| mode | top-5 | first expected rank |")
        lines.append("|---|---|---|")
        for mode in MODES:
            s = row["results"][mode.value]
            lines.append(
                f"| {mode.value} | {' → '.join(s['top_articles'])} | "
                f"{s['first_expected_rank']} |"
            )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="B7: golden retrieval eval")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    args = parser.parse_args()

    logger.info("Starting eval_retrieval.py")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"Embedding model: {settings.EMBEDDING_MODEL}")

    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    cases = golden["queries"]
    logger.info(
        f"golden set v{golden['version']}: {len(cases)} queries, "
        f"pinned_at={golden.get('pinned_at')}"
    )

    unpinned = [c["id"] for c in cases if not c["expected_chunk_ids"]]
    if unpinned:
        logger.error(
            f"golden queries without expected_chunk_ids: {unpinned}. "
            "Answers must be pinned (plan 3.6) before the eval means anything."
        )
        return 2

    rows: list[dict[str, Any]] = []
    client = EmbeddingClient()
    for case in cases:
        row: dict[str, Any] = {
            "id": case["id"],
            "query": case["query"],
            "expected_chunk_ids": case["expected_chunk_ids"],
            "expected_document_id": case.get("expected_document_id"),
            "must_contain_article": case.get("must_contain_article"),
            "results": {},
        }
        # One embedding per query, reused by the two arms that need it. The
        # 1 RPS budget is a team budget: paying three times for the same string
        # would be waste, not thoroughness. BM25 needs no embedding at all.
        qv = embed_query(case["query"], client=client)
        for mode in MODES:
            hits = search(case["query"], top_k=args.top_k, mode=mode, query_vector=qv)
            row["results"][mode.value] = score_query(hits, case, args.top_k)
            logger.info(
                f"[{case['id']}] {mode.value}: {row['results'][mode.value]['top_ids']}"
            )
        rows.append(row)

    per_mode = {
        mode.value: {
            "hit_at_1": mean([r["results"][mode.value]["hit_at_1"] for r in rows]),
            "hit_at_5": mean([r["results"][mode.value]["hit_at_5"] for r in rows]),
            "mrr": mean([r["results"][mode.value]["rr"] for r in rows]),
            "article_at_5": mean(
                [
                    r["results"][mode.value]["article_at_5"]
                    if r["results"][mode.value]["article_at_5"] is not None
                    else 0.0
                    for r in rows
                ]
            ),
        }
        for mode in MODES
    }

    print_table(rows, args.top_k)
    print_summary(per_mode, len(rows))

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "run_at": dt.datetime.now().isoformat(timespec="seconds"),
        "golden_version": golden["version"],
        "golden_pinned_at": golden.get("pinned_at"),
        "n_queries": len(cases),
        "top_k": args.top_k,
        "embedding_model": settings.EMBEDDING_MODEL,
        "summary": per_mode,
        "queries": rows,
    }
    json_path, md_path = write_results(payload, stamp)
    logger.info("")
    logger.info(f"wrote {json_path.relative_to(PROJECT_ROOT)}")
    logger.info(f"wrote {md_path.relative_to(PROJECT_ROOT)}")

    # A convenience smoke check that the agent-facing wrapper behaves like the
    # hybrid arm; the V4-V6 verdict is verify_embeddings.py's job. It embeds
    # the query itself, which is the point: the wrapper takes only a string.
    probe = hybrid_search(cases[0]["query"], top_k=args.top_k)
    logger.info(
        f"hybrid_search() sanity: {cases[0]['id']} -> "
        f"{[h.chunk_id for h in probe]}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
