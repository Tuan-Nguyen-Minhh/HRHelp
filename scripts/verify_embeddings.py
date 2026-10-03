"""Verify V1–V8 for B6 (embeddings) and B7 (hybrid search).

Plan: ``data_pipeline_steps/step6_7_plan.md`` section 4.

Every check recomputes a concrete value from the database, the audit log or the
API — none of them is written to pass. Where a check needs the Mistral API it
says so, and it reuses one embedding per query across all three arms so the
verification itself does not burn the team quota.

  V1      migration + schema: database revisions match the repository head, table exists, ``embedding`` really
          is VECTOR(1024) per ``format_type`` (never per the Python model),
          search_tsv is a GENERATED STORED tsvector, HNSW + GIN exist with the
          frozen parameters, FK cascades, HR columns untouched at 1024
  V2      complete + correct + fresh: EXPECTED_ROWS rows exactly, 0 NULL embeddings,
          every dimensions/vector_dims/model correct, and 100% content_sha256
          equal to the sha256 of the CURRENT legal_chunks.text
  V3      idempotent + quota arithmetic: second run skips every row and issues zero
          API calls (proved from the audit log, not from the script's stdout),
          md5 of all vectors unchanged; one edited text re-embeds exactly
          one row and the new sha matches
  V4      vector golden: every expected_chunk_id inside vector-only top-5; all
          norms finite; 5 re-embedded sample chunks at cosine >= 0.999
  V5      BM25 + hybrid: must_contain_article of every query in the top-5 of all
          three arms; RRF k=60 proven by a unit test on fake input, no DB
  V6      metrics floor: hybrid Hit@5 >= 0.8 and MRR >= 0.6, and hybrid not
          behind either single arm by more than 0.1 on either metric
  V7      quota + resume: corpus tokens <= 1M, every logged request gap >= 1.0s,
          and a process killed mid-run resumes to EXPECTED_ROWS with no duplicates
  V8      source untouched + no regression: the 8 frozen JSON files match
          source_manifest.json, verify_db.py still 70/70, mutation_test.py
          still 18/18

V-manual (reading the top-5 of all 10 queries by hand and signing
``eval/verify_retrieval_manual.md``) is a separate step outside this loop, the
same way V5-manual is for B4/B5.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import corpus_expectations  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.models.legal import EMBEDDING_DIM, EMBEDDING_MODEL_NAME  # noqa: E402
from src.services.embeddings_client import (  # noqa: E402
    API_CALL_LOG,
    PURPOSE_CORPUS,
    PURPOSE_PROBE,
    EmbeddingClient,
    read_call_log,
)
from src.services.hybrid_search import (  # noqa: E402
    DEFAULT_TOP_K,
    RRF_K,
    SearchMode,
    cosine_similarity,
    reciprocal_rank_fusion,
    search,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("verify_embeddings")

_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)

CHUNK_DIR = PROJECT_ROOT / "data" / "chunk"
GOLDEN_PATH = PROJECT_ROOT / "eval" / "legal_golden.json"
MANIFEST_PATH = CHUNK_DIR / "source_manifest.json"
SOURCE_FILES = corpus_expectations.CHUNK_FILES + corpus_expectations.TREE_FILES

# Expectations (plan 1 / 2). Derived from data/chunk/chunks_*.json, never from
# the DB — recomputing from the DB would make each equality below trivially
# true. See scripts/corpus_expectations.py.
EXPECTED_ROWS = corpus_expectations.TOTAL_CHUNKS
EXPECTED_CHUNKS = corpus_expectations.TOTAL_CHUNKS
EXPECTED_MODEL = EMBEDDING_MODEL_NAME
EXPECTED_DIM = EMBEDDING_DIM

# V6 floor (plan 3.7 / section 4). Regression guard, not a quality target.
MIN_HYBRID_HIT_AT_5 = 0.8
MIN_HYBRID_MRR = 0.6
MAX_LOSS_TO_SINGLE_ARM = 0.1

# V7 quota (plan 2.2 / section 4).
MAX_CORPUS_TOKENS = 1_000_000
MIN_REQUEST_GAP_S = 1.0

# V4 knowledge-control: a re-embed of the same text must land on the same
# vector, whatever key/model is in .env. Catches a silent model or key swap.
MIN_REEMBED_COSINE = 0.999
REEMBED_SAMPLE = 5

# V7 crash test sizing: 96 rows == exactly 3 batches of 32, so a kill lands
# mid-run with committed and uncommitted work both present.
CRASH_TEST_ROWS = 96
CRASH_TEST_WAIT_S = 2.5

results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> bool:
    results.append((name, passed, detail))
    logger.info(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    return passed


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_script(name: str, *args: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / name), *args]
    logger.info(f"  $ {' '.join(cmd)}")
    return subprocess.run(
        cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout
    )


def log_line_count() -> int:
    return len(read_call_log())


def vector_fingerprint(db: Session) -> str:
    """md5 over every stored vector, keyed by chunk_id.

    Deliberately content-based, not row-order based, so the comparison cannot be
    fooled by a reordering.
    """
    return db.execute(
        sa.text(
            "SELECT md5(string_agg(chunk_id || ':' || md5(embedding::text), '|' "
            "                ORDER BY chunk_id)) "
            "FROM legal_chunk_embeddings"
        )
    ).scalar()


def total_rows(db: Session) -> int:
    return db.scalar(sa.text("SELECT count(*) FROM legal_chunk_embeddings"))


def alembic_head() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception as exc:  # pragma: no cover
        logger.error(f"  could not resolve alembic head: {exc}")
        return None


def load_golden() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["queries"]


# ---------------------------------------------------------------------------
# V1: migration + schema
# ---------------------------------------------------------------------------

def verify_v1(db: Session) -> None:
    logger.info("--- V1: migration + schema ---")
    try:
        db.execute(sa.text("SELECT 1"))
        record("V1.connection", True, "SELECT 1 ok")
    except Exception as exc:
        record("V1.connection", False, str(exc))
        return

    head = alembic_head()
    current = list(db.scalars(sa.text("SELECT version_num FROM alembic_version")))
    record(
        "V1.alembic_current_eq_head",
        head is not None and current == [head],
        f"current={current} head={head}",
    )

    exists = db.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='legal_chunk_embeddings')"
        )
    ).scalar()
    record("V1.table_exists", bool(exists), f"exists={exists}")
    if not exists:
        return

    # The real column type, read from the catalogue. Trusting the ORM class
    # would only prove that the ORM class says Vector(1024).
    cols = {
        r[0]: (r[1], r[2])
        for r in db.execute(
            sa.text(
                "SELECT attname, format_type(atttypid, atttypmod), attgenerated "
                "FROM pg_attribute WHERE attrelid='legal_chunk_embeddings'::regclass "
                "AND attnum > 0 AND NOT attisdropped"
            )
        )
    }
    record(
        "V1.embedding_is_vector1024",
        cols.get("embedding", ("", ""))[0] == f"vector({EXPECTED_DIM})",
        f"format_type={cols.get('embedding', ('<missing>', ''))[0]}",
    )
    record(
        "V1.content_sha256_is_char64",
        cols.get("content_sha256", ("", ""))[0] == "character(64)",
        f"format_type={cols.get('content_sha256', ('<missing>', ''))[0]}",
    )
    record(
        "V1.search_tsv_is_generated_stored",
        cols.get("search_tsv", ("", ""))[0] == "tsvector"
        and cols.get("search_tsv", ("", ""))[1] == "s",
        f"type={cols.get('search_tsv', ('<missing>', ''))[0]} "
        f"attgenerated={cols.get('search_tsv', ('', '<missing>'))[1]} "
        "(expected 's' = GENERATED ALWAYS STORED)",
    )
    for col, want in (
        ("chunk_id", "character varying(128)"),
        ("model", "character varying(64)"),
        ("dimensions", "integer"),
        ("header_context", "text"),
        ("text", "text"),
    ):
        record(
            f"V1.column_{col}",
            cols.get(col, ("", ""))[0] == want,
            f"got={cols.get(col, ('<missing>', ''))[0]} want={want}",
        )

    # FK to legal_chunks with ON DELETE CASCADE
    fk = db.execute(
        sa.text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conrelid='legal_chunk_embeddings'::regclass AND contype='f'"
        )
    ).scalar()
    record(
        "V1.fk_cascade_to_legal_chunks",
        fk == "c",
        f"confdeltype={fk} (expected 'c' = CASCADE)",
    )

    checks = {
        r[0]: r[1]
        for r in db.execute(
            sa.text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='legal_chunk_embeddings'::regclass"
            )
        )
    }
    record(
        "V1.dimensions_check",
        any(
            n == "ck_legal_chunk_embeddings_dimensions" and f"= {EXPECTED_DIM}" in d
            for n, d in checks.items()
        ),
        f"{checks.get('ck_legal_chunk_embeddings_dimensions', '<missing>')}",
    )

    idx = {
        r[0]: r[1]
        for r in db.execute(
            sa.text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename='legal_chunk_embeddings'"
            )
        )
    }
    hnsw = idx.get("ix_legal_embeddings_hnsw", "")
    record(
        "V1.hnsw_index",
        "hnsw" in hnsw
        and "vector_cosine_ops" in hnsw
        and "m='16'" in hnsw
        and "ef_construction='64'" in hnsw,
        f"{hnsw}",
    )
    gin = idx.get("ix_legal_chunk_embeddings_search_tsv", "")
    record("V1.gin_index", "USING gin" in gin and "search_tsv" in gin, f"{gin}")

    # HR Help columns must be untouched by B6 (plan section 6).
    for table in ("document_chunks", "disciplinary_decisions"):
        t = db.execute(
            sa.text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid=CAST(:t AS regclass) AND attname='embedding' "
                "AND NOT attisdropped"
            ),
            {"t": table},
        ).scalar()
        record(
            f"V1.hr_{table}_still_vector1024",
            t == f"vector({EXPECTED_DIM})",
            f"{table}.embedding={t}",
        )


# ---------------------------------------------------------------------------
# V2: complete + correct + fresh
# ---------------------------------------------------------------------------

def verify_v2(db: Session, label: str = "") -> None:
    tag = f"V2{'.' + label if label else ''}"
    logger.info(f"--- {tag}: complete + correct + fresh ---")

    total = db.scalar(sa.text("SELECT count(*) FROM legal_chunk_embeddings"))
    record(f"{tag}.row_count", total == EXPECTED_ROWS, f"expected={EXPECTED_ROWS} got={total}")

    n_chunks = db.scalar(sa.text("SELECT count(*) FROM legal_chunks"))
    record(
        f"{tag}.covers_every_chunk",
        total == n_chunks == EXPECTED_CHUNKS,
        f"embeddings={total} chunks={n_chunks} expected={EXPECTED_CHUNKS}",
    )

    nulls = db.scalar(
        sa.text("SELECT count(*) FROM legal_chunk_embeddings WHERE embedding IS NULL")
    )
    record(f"{tag}.no_null_embedding", nulls == 0, f"nulls={nulls}")

    bad_dim = db.scalar(
        sa.text(
            f"SELECT count(*) FROM legal_chunk_embeddings WHERE dimensions <> {EXPECTED_DIM}"
        )
    )
    record(f"{tag}.dimensions_column", bad_dim == 0, f"wrong={bad_dim}")

    bad_vec = db.scalar(
        sa.text("SELECT count(*) FROM legal_chunk_embeddings WHERE vector_dims(embedding) <> :d"),
        {"d": EXPECTED_DIM},
    )
    record(
        f"{tag}.vector_dims",
        bad_vec == 0,
        f"rows whose vector_dims <> {EXPECTED_DIM}: {bad_vec}",
    )

    bad_model = db.scalar(
        sa.text("SELECT count(*) FROM legal_chunk_embeddings WHERE model <> :m"),
        {"m": EXPECTED_MODEL},
    )
    record(f"{tag}.model", bad_model == 0, f"rows with model <> {EXPECTED_MODEL}: {bad_model}")

    orphans = db.scalar(
        sa.text(
            "SELECT count(*) FROM legal_chunk_embeddings e "
            "WHERE NOT EXISTS (SELECT 1 FROM legal_chunks c WHERE c.chunk_id = e.chunk_id)"
        )
    )
    record(f"{tag}.no_orphans", orphans == 0, f"orphans={orphans}")

    # The staleness detector. Computed in Python from the current text, not
    # compared against a stored copy of itself.
    mismatched: list[str] = []
    rows = db.execute(
        sa.text(
            "SELECT e.chunk_id, e.content_sha256, c.text FROM legal_chunk_embeddings e "
            "JOIN legal_chunks c ON c.chunk_id = e.chunk_id"
        )
    )
    n = 0
    for chunk_id, stored_sha, text in rows:
        n += 1
        if (stored_sha or "").strip() != sha256_text(text):
            mismatched.append(chunk_id)
    record(
        f"{tag}.content_sha256_fresh",
        not mismatched and n == EXPECTED_ROWS,
        f"checked={n} mismatched={len(mismatched)} {mismatched[:5]}",
    )

    # The denormalised copies must equal their originals byte for byte. They
    # exist so the GENERATED tsvector can be stored and indexed; if they drift
    # from legal_chunks, BM25 would rank against text that is not the corpus.
    drift = db.scalar(
        sa.text(
            "SELECT count(*) FROM legal_chunk_embeddings e JOIN legal_chunks c "
            "ON c.chunk_id = e.chunk_id "
            "WHERE e.text IS DISTINCT FROM c.text "
            "   OR e.header_context IS DISTINCT FROM c.header_context"
        )
    )
    record(f"{tag}.denormalised_text_matches", drift == 0, f"drifted rows={drift}")


# ---------------------------------------------------------------------------
# V3: idempotent + quota arithmetic
# ---------------------------------------------------------------------------

def verify_v3(db: Session) -> None:
    logger.info("--- V3: idempotent + quota arithmetic ---")
    before_fp = vector_fingerprint(db)
    before_log = log_line_count()
    logger.info(f"  vector md5 before : {before_fp}")
    logger.info(f"  audit log lines   : {before_log}")

    proc = run_script("embed_legal.py")
    record("V3.rerun_exit_zero", proc.returncode == 0, f"returncode={proc.returncode}")
    if proc.returncode != 0:
        logger.error(proc.stdout[-2000:])
        logger.error(proc.stderr[-2000:])
        return

    # How many chunks *needed* embedding is read from the database, not from the
    # script's own stdout: a fresh hash means "would have been skipped".
    stale = 0
    for chunk_id, stored_sha, text in db.execute(
        sa.text(
            "SELECT e.chunk_id, e.content_sha256, c.text FROM legal_chunk_embeddings e "
            "JOIN legal_chunks c ON c.chunk_id = e.chunk_id"
        )
    ):
        if (stored_sha or "").strip() != sha256_text(text):
            stale += 1
    record(
        "V3.skipped_equals_all_rows",
        stale == 0 and total_rows(db) == EXPECTED_ROWS,
        f"chunks with a stale hash after the rerun={stale} (so skipped="
        f"{EXPECTED_ROWS - stale}), rows={total_rows(db)}",
    )

    after_fp = vector_fingerprint(db)
    after_log = log_line_count()
    # Zero new API calls, proved by the audit log — not by trusting the
    # "skipped (fresh): N" line the script printed about itself.
    record(
        "V3.zero_new_api_requests",
        after_log == before_log,
        f"audit log lines {before_log} -> {after_log}",
    )
    record(
        "V3.vector_md5_unchanged",
        before_fp == after_fp,
        f"before={before_fp} after={after_fp}",
    )

    # One edited text must re-embed exactly one row.
    target = db.execute(
        sa.text("SELECT chunk_id, text FROM legal_chunks ORDER BY chunk_id LIMIT 1")
    ).first()
    cid, original_text = target[0], target[1]
    original_sha = sha256_text(original_text)
    edited_text = original_text + " [V3 probe]"
    # execute + commit, not db.begin(): the session already has an implicit
    # transaction open from the reads above, and Session.begin() raises on that.
    db.execute(
        sa.text("UPDATE legal_chunks SET text=:t WHERE chunk_id=:c"),
        {"t": edited_text, "c": cid},
    )
    db.commit()
    before_log = log_line_count()
    proc = run_script("embed_legal.py")
    record("V3.edit_rerun_exit_zero", proc.returncode == 0, f"returncode={proc.returncode}")

    new_log = log_line_count()
    record(
        "V3.edit_costs_exactly_one_request",
        new_log - before_log == 1,
        f"new audit log lines={new_log - before_log} (expected 1)",
    )
    stored = db.execute(
        sa.text("SELECT content_sha256, embedding::text FROM legal_chunk_embeddings WHERE chunk_id=:c"),
        {"c": cid},
    ).first()
    record(
        "V3.edit_new_sha_matches",
        (stored[0] or "").strip() == sha256_text(edited_text),
        f"stored={(stored[0] or '').strip()[:16]}… expected={sha256_text(edited_text)[:16]}…",
    )

    # Restore, then re-embed and require the vector to come back to itself.
    db.execute(
        sa.text("UPDATE legal_chunks SET text=:t WHERE chunk_id=:c"),
        {"t": original_text, "c": cid},
    )
    db.commit()
    run_script("embed_legal.py")
    restored = db.execute(
        sa.text("SELECT content_sha256 FROM legal_chunk_embeddings WHERE chunk_id=:c"),
        {"c": cid},
    ).scalar()
    record(
        "V3.restore_sha_matches",
        (restored or "").strip() == original_sha,
        f"chunk={cid}",
    )
    after_fp = vector_fingerprint(db)
    record(
        "V3.vector_fingerprint_restored",
        before_fp == after_fp,
        f"before={before_fp} after={after_fp} (identical vectors are re-derived, "
        "not restored from a backup)",
    )


# ---------------------------------------------------------------------------
# V4/V5/V6: retrieval quality — one measurement, three verdicts
# ---------------------------------------------------------------------------

def measure_arms(cases: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    """Run every case through all three arms, one embedding per query."""
    client = EmbeddingClient()
    from src.services.hybrid_search import embed_query

    per_case: list[dict[str, Any]] = []
    for case in cases:
        qv = embed_query(case["query"], client=client)
        row: dict[str, Any] = {"case": case, "arms": {}}
        for mode in (SearchMode.VECTOR, SearchMode.BM25, SearchMode.HYBRID):
            hits = search(case["query"], top_k=top_k, mode=mode, query_vector=qv)
            ids = [h.chunk_id for h in hits]
            expected = set(case["expected_chunk_ids"])
            rank = next((i for i, x in enumerate(ids, 1) if x in expected), None)
            doc, art = case.get("expected_document_id"), case.get("must_contain_article")
            row["arms"][mode.value] = {
                "ids": ids,
                "articles": [f"{h.document_id}#D{h.article_number}" for h in hits],
                "rank": rank,
                "hit_at_1": 1.0 if rank == 1 else 0.0,
                "hit_at_5": 1.0 if rank is not None else 0.0,
                "rr": (1.0 / rank) if rank else 0.0,
                "article_at_5": bool(
                    doc is not None
                    and art is not None
                    and any(
                        h.document_id == doc and h.article_number == art for h in hits
                    )
                ),
            }
        per_case.append(row)
    return {"cases": per_case}


def verify_v4(db: Session, measured: dict[str, Any], top_k: int) -> None:
    logger.info("--- V4: vector-only golden ---")
    misses = [
        (r["case"]["id"], r["arms"]["vector"]["ids"])
        for r in measured["cases"]
        if r["arms"]["vector"]["hit_at_5"] == 0.0
    ]
    record(
        "V4.vector_top5_contains_expected",
        not misses,
        f"queries missing an expected chunk in vector-only top-{top_k}: "
        f"{[m[0] for m in misses]}",
    )
    for r in measured["cases"]:
        logger.info(
            f"  [{r['case']['id']}] vector top-{top_k}: {r['arms']['vector']['articles']}"
        )

    # Knowledge control 1: no NaN/Inf anywhere. A self-distance of NaN is the
    # signature of a non-finite component, and `NaN = 0` is false in Postgres.
    nonfinite = db.scalar(
        sa.text(
            "SELECT count(*) FROM legal_chunk_embeddings "
            "WHERE NOT ((embedding <=> embedding) = 0)"
        )
    )
    record("V4.all_norms_finite", nonfinite == 0, f"non-finite vectors={nonfinite}")

    norms = db.execute(
        sa.text(
            "SELECT chunk_id, embedding::text FROM legal_chunk_embeddings "
            "ORDER BY chunk_id LIMIT 64"
        )
    )
    bad_norm: list[str] = []
    for chunk_id, vec_text in norms:
        vals = [float(x) for x in vec_text.strip("[]").split(",")]
        n = math.sqrt(sum(v * v for v in vals))
        if not math.isfinite(n):
            bad_norm.append(chunk_id)
    record(
        "V4.sample_norms_finite",
        not bad_norm,
        f"checked 64 rows, non-finite norms={len(bad_norm)}",
    )

    # Knowledge control 2: re-embed a few chunks and require cosine >= 0.999.
    # A silent key/model swap would still produce finite, plausible-looking
    # vectors; only a same-input comparison catches it.
    sample = db.execute(
        sa.text(
            "SELECT chunk_id, header_context, text, embedding::text "
            "FROM legal_chunk_embeddings ORDER BY chunk_id LIMIT :n"
        ),
        {"n": REEMBED_SAMPLE},
    ).all()
    texts = [f"{h}\n{t}" if h else t for _, h, t, _ in sample]
    client = EmbeddingClient()
    fresh = client.embed(
        texts, purpose=PURPOSE_PROBE, run_id="verify-v4-reembed", chunk_ids=[s[0] for s in sample]
    )
    worst = 1.0
    worst_id = ""
    for (cid, _, _, stored_text), vec in zip(sample, fresh, strict=True):
        stored = [float(x) for x in stored_text.strip("[]").split(",")]
        cos = cosine_similarity(stored, vec)
        if cos < worst:
            worst, worst_id = cos, cid
    record(
        "V4.reembed_cosine",
        worst >= MIN_REEMBED_COSINE,
        f"worst cosine={worst:.6f} on {worst_id} (floor {MIN_REEMBED_COSINE}, "
        f"{REEMBED_SAMPLE} chunks re-embedded)",
    )


def verify_v5(measured: dict[str, Any], top_k: int) -> None:
    logger.info("--- V5: BM25 + hybrid ---")
    for mode in ("vector", "bm25", "hybrid"):
        bad = [
            r["case"]["id"]
            for r in measured["cases"]
            if not r["arms"][mode]["article_at_5"]
        ]
        record(
            f"V5.article_in_top{top_k}.{mode}",
            not bad,
            f"queries whose must_contain_article is absent from {mode} top-{top_k}: {bad}",
        )

    # RRF formula, unit-tested on fake input with no database involved.
    record("V5.rrf_k_is_60", RRF_K == 60, f"RRF_K={RRF_K}")
    a = ["d1", "d2", "d3"]
    b = ["d3", "d1", "d4"]
    fused = dict(reciprocal_rank_fusion([a, b]))
    # d1: rank 1 in a, rank 2 in b -> 1/61 + 1/62
    # d2: rank 2 in a, absent in b -> 1/62
    # d3: rank 3 in a, rank 1 in b -> 1/63 + 1/61
    # d4: rank 3 in b, absent in a -> 1/63
    record(
        "V5.rrf_formula",
        abs(fused["d1"] - (1 / 61 + 1 / 62)) < 1e-12
        and abs(fused["d2"] - 1 / 62) < 1e-12
        and abs(fused["d3"] - (1 / 63 + 1 / 61)) < 1e-12
        and abs(fused["d4"] - 1 / 63) < 1e-12,
        f"d1={fused['d1']:.6f} d2={fused['d2']:.6f} d3={fused['d3']:.6f} "
        f"d4={fused['d4']:.6f} (expect 1/61+1/62, 1/62, 1/63+1/61, 1/63)",
    )
    record(
        "V5.rrf_ranks_are_1_based",
        abs(dict(reciprocal_rank_fusion([["x"]]))["x"] - 1 / 61) < 1e-12,
        "single arm, rank 1 -> 1/(k+1) = 1/61",
    )
    # d1 (0.032522) > d3 (0.032266) > d2 (0.016129) > d4 (0.015873): being high
    # in one arm beats being high in both at a lower rank, and the tiebreak by
    # chunk_id never fires here.
    order = [cid for cid, _ in reciprocal_rank_fusion([a, b])]
    record(
        "V5.rrf_order",
        order == ["d1", "d3", "d2", "d4"],
        f"order={order} (expected by descending score, not by any single arm)",
    )
    tied = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
    record(
        "V5.rrf_tiebreak_deterministic",
        [cid for cid, _ in tied] == ["a", "b"],
        f"symmetric input resolves to {[cid for cid, _ in tied]} (ties broken by id)",
    )
    empty = reciprocal_rank_fusion([[], []])
    record("V5.rrf_empty_input", empty == [], f"empty arms -> {empty}")
    try:
        reciprocal_rank_fusion([["a"]], k=0)
        record("V5.rrf_rejects_k_zero", False, "k=0 did not raise")
    except ValueError:
        record("V5.rrf_rejects_k_zero", True, "k=0 raises ValueError")


def verify_v6(measured: dict[str, Any]) -> None:
    logger.info("--- V6: metrics floor ---")
    n = len(measured["cases"])
    summary = {
        mode: {
            "hit_at_5": sum(r["arms"][mode]["hit_at_5"] for r in measured["cases"]) / n,
            "mrr": sum(r["arms"][mode]["rr"] for r in measured["cases"]) / n,
            "hit_at_1": sum(r["arms"][mode]["hit_at_1"] for r in measured["cases"]) / n,
            "article_at_5": sum(
                1.0 if r["arms"][mode]["article_at_5"] else 0.0 for r in measured["cases"]
            )
            / n,
        }
        for mode in ("vector", "bm25", "hybrid")
    }
    for mode, m in summary.items():
        logger.info(
            f"  {mode:<7} Hit@1={m['hit_at_1']:.3f} Hit@5={m['hit_at_5']:.3f} "
            f"MRR={m['mrr']:.3f} Article@5={m['article_at_5']:.3f}"
        )

    record(
        "V6.hybrid_hit_at_5_floor",
        summary["hybrid"]["hit_at_5"] >= MIN_HYBRID_HIT_AT_5,
        f"hybrid Hit@5={summary['hybrid']['hit_at_5']:.3f} "
        f"(floor {MIN_HYBRID_HIT_AT_5})",
    )
    record(
        "V6.hybrid_mrr_floor",
        summary["hybrid"]["mrr"] >= MIN_HYBRID_MRR,
        f"hybrid MRR={summary['hybrid']['mrr']:.3f} (floor {MIN_HYBRID_MRR})",
    )
    for single in ("vector", "bm25"):
        for metric in ("hit_at_5", "mrr"):
            loss = summary[single][metric] - summary["hybrid"][metric]
            record(
                f"V6.hybrid_not_behind_{single}.{metric}",
                loss <= MAX_LOSS_TO_SINGLE_ARM,
                f"hybrid {summary['hybrid'][metric]:.3f} vs {single} "
                f"{summary[single][metric]:.3f} -> loss {loss:+.3f} "
                f"(allowed {MAX_LOSS_TO_SINGLE_ARM})",
            )


# ---------------------------------------------------------------------------
# V7: quota + resume
# ---------------------------------------------------------------------------

def verify_v7(db: Session) -> None:
    logger.info("--- V7: quota + resume ---")
    recs = read_call_log()
    corpus = [r for r in recs if r.get("purpose") == PURPOSE_CORPUS]

    # The quota ceiling is about *building* the corpus, not about every probe a
    # verification run ever spends. The build is the single corpus-purpose run
    # that cost the most tokens — the initial backfill. Probes (V3's deliberate
    # one-chunk re-embed, V7's crash-test re-embed, V8's cascade repair) are
    # reported separately and never folded into the ceiling, but they are still
    # printed, because hiding them would make the log look tidier than reality.
    per_run: dict[str, int] = {}
    for r in corpus:
        per_run[r.get("run_id", "?")] = per_run.get(r.get("run_id", "?"), 0) + (
            r.get("prompt_tokens") or 0
        )
    build_run, build_tokens = (
        max(per_run.items(), key=lambda kv: kv[1]) if per_run else (None, 0)
    )
    all_time = sum(per_run.values())
    logger.info(f"  audit log: {len(recs)} request(s) total, {len(corpus)} corpus")
    logger.info(f"  corpus run ids: {len(per_run)}; tokens by run: {per_run}")
    logger.info(
        f"  build run (largest) = {build_run}: {build_tokens} tokens | "
        f"all-time corpus-purpose total = {all_time} tokens"
    )
    record(
        "V7.corpus_tokens_under_ceiling",
        build_tokens <= MAX_CORPUS_TOKENS,
        f"build run {build_run} spent {build_tokens} prompt tokens "
        f"(ceiling {MAX_CORPUS_TOKENS}); all-time corpus-purpose total "
        f"{all_time} including verification re-embeds",
    )
    errors = [r for r in recs if r.get("status") != "ok"]
    record("V7.no_failed_requests", not errors, f"failed calls={len(errors)}")

    epochs = sorted(float(r["epoch"]) for r in recs if "epoch" in r)
    gaps = [round(b - a, 4) for a, b in zip(epochs, epochs[1:])]
    if gaps:
        logger.info(f"  min request gap={min(gaps)}s over {len(gaps)} consecutive pairs")
    record(
        "V7.min_request_gap",
        bool(gaps) and min(gaps) >= MIN_REQUEST_GAP_S,
        f"min gap={min(gaps) if gaps else 'n/a'}s (floor {MIN_REQUEST_GAP_S}s) "
        f"across {len(gaps)} consecutive requests",
    )

    # Crash test: drop a slice of rows, start the real CLI, kill it mid-run,
    # then run it again and require a complete, duplicate-free table.
    victims = [
        r[0]
        for r in db.execute(
            sa.text(
                "SELECT chunk_id FROM legal_chunk_embeddings ORDER BY chunk_id LIMIT :n"
            ),
            {"n": CRASH_TEST_ROWS},
        )
    ]
    db.execute(
        sa.text("DELETE FROM legal_chunk_embeddings WHERE chunk_id = ANY(:ids)"),
        {"ids": victims},
    )
    db.commit()
    removed = db.scalar(sa.text("SELECT count(*) FROM legal_chunk_embeddings"))
    logger.info(
        f"  crash test: deleted {len(victims)} row(s) -> {removed} left, "
        f"killing the CLI after {CRASH_TEST_WAIT_S}s"
    )

    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "embed_legal.py")]
    proc = subprocess.Popen(
        cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(CRASH_TEST_WAIT_S)
    killed = proc.poll() is None
    proc.kill()
    try:
        out, _ = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:  # pragma: no cover
        proc.kill()
        out, _ = proc.communicate(timeout=30)
    mid = db.scalar(sa.text("SELECT count(*) FROM legal_chunk_embeddings"))
    logger.info(
        f"  after kill: killed_while_running={killed}, rows={mid}, "
        f"returncode={proc.returncode}"
    )
    record(
        "V7.killed_mid_run",
        killed and proc.returncode not in (0, None),
        f"process was still running after {CRASH_TEST_WAIT_S}s and was killed "
        f"(returncode={proc.returncode}); {mid} rows survived the partial run",
    )

    resume = run_script("embed_legal.py")
    record("V7.resume_exit_zero", resume.returncode == 0, f"returncode={resume.returncode}")
    if resume.returncode != 0:
        logger.error(resume.stdout[-2000:])
        logger.error(resume.stderr[-2000:])

    total = db.scalar(sa.text("SELECT count(*) FROM legal_chunk_embeddings"))
    record(
        "V7.resume_restores_full_count",
        total == EXPECTED_ROWS,
        f"rows={total} expected={EXPECTED_ROWS}",
    )
    dups = db.execute(
        sa.text(
            "SELECT count(*) FROM (SELECT chunk_id FROM legal_chunk_embeddings "
            "GROUP BY chunk_id HAVING count(*) > 1) d"
        )
    ).scalar()
    record("V7.no_duplicate_rows", dups == 0, f"duplicated chunk_ids={dups}")

    still_missing = [
        r[0] for r in db.execute(
            sa.text(
                "SELECT c.chunk_id FROM legal_chunks c "
                "WHERE NOT EXISTS (SELECT 1 FROM legal_chunk_embeddings e "
                "WHERE e.chunk_id = c.chunk_id) ORDER BY c.chunk_id"
            )
        )
    ]
    record(
        "V7.every_chunk_has_a_vector",
        not still_missing,
        f"chunks without a vector after resume: {still_missing[:5]}",
    )

    # The resumed rows must be FRESH, not merely present. content_sha256 is
    # recomputed in Python from the current legal_chunks.text for exactly the
    # rows the crash test destroyed — the same way V2 does it for the whole corpus.
    resumed_stale = [
        cid
        for cid, stored_sha, text in db.execute(
            sa.text(
                "SELECT e.chunk_id, e.content_sha256, c.text "
                "FROM legal_chunk_embeddings e JOIN legal_chunks c "
                "ON c.chunk_id = e.chunk_id WHERE e.chunk_id = ANY(:ids)"
            ),
            {"ids": victims},
        )
        if (stored_sha or "").strip() != sha256_text(text)
    ]
    record(
        "V7.resumed_rows_fresh",
        not resumed_stale,
        f"re-embedded {len(victims)} row(s), stale among them: "
        f"{len(resumed_stale)} {resumed_stale[:5]}",
    )


# ---------------------------------------------------------------------------
# V8: source untouched + no regression
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def verify_v8() -> None:
    logger.info("--- V8: source untouched + no regression ---")
    manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["files"]
        if MANIFEST_PATH.exists()
        else None
    )
    record("V8.manifest_exists", manifest is not None, str(MANIFEST_PATH.name))
    if manifest:
        now = {f: sha256_file(CHUNK_DIR / f) for f in SOURCE_FILES if (CHUNK_DIR / f).exists()}
        drifted = sorted(f for f, h in manifest.items() if now.get(f) != h)
        absent = sorted(set(manifest) - set(now))
        for f, h in manifest.items():
            logger.info(f"  [{'OK  ' if now.get(f) == h else 'DIFF'}] {f}: {h[:16]}…")
        record(
            "V8.sources_match_pinned_manifest",
            not drifted and not absent and len(now) == len(SOURCE_FILES),
            f"drifted={drifted} absent={absent} present={len(now)}/{len(SOURCE_FILES)}",
        )

    proc = run_script("verify_db.py")
    fails = sorted(
        {
            line.split("[FAIL] ", 1)[1].split(":", 1)[0]
            for line in (proc.stdout + proc.stderr).splitlines()
            if "[FAIL]" in line
        }
    )
    record(
        "V8.verify_db_still_70_of_70",
        proc.returncode == 0 and not fails,
        f"exit={proc.returncode} fails={fails[:8]} (B4/B5 must not regress)",
    )

    proc = run_script("mutation_test.py", timeout=3600)
    # logging.basicConfig writes to STDERR, so the [CAUGHT]/[MISSED] markers are
    # not in stdout. Counting stdout alone reported "caught=0" on a run that had
    # actually caught everything.
    combined = proc.stdout + proc.stderr
    caught = combined.count("[CAUGHT]")
    missed = combined.count("[MISSED]")
    record(
        "V8.mutation_test_still_18_of_18",
        proc.returncode == 0 and caught == 18 and missed == 0,
        f"exit={proc.returncode} caught={caught}/18 missed={missed}",
    )
    if proc.returncode != 0 or caught != 18:
        # Surface the tail so a failure here is diagnosable from the log alone
        # instead of "exit=1 caught=0" with nothing to go on.
        logger.error("mutation_test.py tail:")
        logger.error(combined[-3000:])

    # Restore whatever V8 destroyed. mutation 'V3.BLLD.count' DELETEs a
    # legal_chunks row and the embeddings FK is ON DELETE CASCADE, so the
    # corpus is one row short after the mutation suite. That is the designed
    # behaviour, not damage — but a verify that leaves the table short would be
    # reporting green on a database that is no longer usable, so the resume is
    # run here and the final V2 re-check proves it closed.
    proc = run_script("embed_legal.py")
    record(
        "V8.restore_after_mutations",
        proc.returncode == 0,
        f"embed_legal.py exit={proc.returncode} (re-embeds rows cascade-deleted by V8)",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    results.clear()
    logger.info("Starting verify_embeddings.py")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info(f"Model: {settings.EMBEDDING_MODEL} ({settings.EMBEDDING_DIMENSIONS}-dim)")
    logger.info(f"Audit log: {API_CALL_LOG.relative_to(PROJECT_ROOT)}")

    cases = load_golden()
    logger.info(f"golden set: {len(cases)} queries")
    top_k = DEFAULT_TOP_K

    db: Session = SessionLocal()
    try:
        verify_v1(db)
        verify_v2(db)
        if any(not passed for _, passed, _ in results):
            logger.error("Prerequisite checks failed. Run alembic upgrade head, seed_legal.py, "
                         "and embed_legal.py successfully before full verification.")
            return 1
        verify_v3(db)
        if any(not passed for _, passed, _ in results):
            logger.error("Embedding rerun checks failed; skipping API and mutation checks.")
            return 1
        measured = measure_arms(cases, top_k)
        verify_v4(db, measured, top_k)
        verify_v5(measured, top_k)
        verify_v6(measured)
        verify_v7(db)
    except Exception as exc:
        logger.error("Verification stopped: %s", exc)
        logger.error("For a Mistral 401, correct MISTRAL_API_KEY in .env or the shell environment.")
        return 1
    finally:
        db.close()

    verify_v8()

    # Final state re-check: V3 and V7 mutate the table and V8 destroys a row on
    # purpose. The milestone is only green if the table is whole again.
    final: Session = SessionLocal()
    try:
        verify_v2(final, label="final")
    finally:
        final.close()

    passed = sum(1 for _, p, _ in results if p)
    failed = len(results) - passed
    logger.info("")
    logger.info("=" * 72)
    logger.info("SUMMARY")
    logger.info("=" * 72)
    for name, p, detail in results:
        logger.info(f"  [{'PASS' if p else 'FAIL'}] {name}: {detail}")
    logger.info("")
    logger.info(f"Total: {passed} PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
