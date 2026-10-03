"""Verify V1-V7 for the B4+B5 seed.

Tightened to match `data_pipeline_steps/step4_5_plan.md` REV.2 exactly. Every
check asserts a concrete, recomputed value — no check is hard-coded to pass.

Counts (chunks / articles / refs, per document and total) are derived from
`data/chunk/chunks_*.json` by `scripts/corpus_expectations.py`, so they follow a
deliberate source change instead of rotting in a literal. See that module for
why the sha256 pins — not these numbers — are the real tripwire.

  V1      connection + migration: alembic current == head, 3 tables, vector ext
  V2      legal_documents: one row per corpus document; BLLD PARTIALLY_AMENDED;
          ND ACTIVE; NQCT ACTIVE (NOI_QUY/VAN_BAN_NOI_BO); amended_by BLLD
          non-null; chunk_count/article_count cross-checked against real rows
  V3      legal_chunks: per-doc counts derived from source; 0 empty; 0 dup id;
          article coverage against document_tree (tree is the expectation)
  V3-bis  special columns: seed=42, 30 chunk ids PRINTED IN FULL, JSON<->DB 100%
  V3-ter  dangling parent: DB count == JSON count (both printed)
  V4      refs: per-doc counts derived from source; target_doc valid; internal
          article exists; anchor level matches ref granularity
  V4-bis  UNRESOLVED == 0
  V4-ter  BOUNDARY budget == 3 AND UNRESOLVED == 0 (hand-pinned: cross-ref policy)
  V5-auto 5 fixed traversal cases with HARD assertions
  V6      idempotent: runs the real CLI in a subprocess, counts unchanged,
          0 stale rows
  V7      source untouched: sha256 vs source_manifest.json pins, before/after
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import corpus_expectations  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.models.legal import (  # noqa: E402
    DOC_STATUS_ACTIVE,
    DOC_STATUS_PARTIALLY_AMENDED,
    LegalChunk,
    LegalChunkReference,
    LegalDocument,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("verify_db")

_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)

CHUNK_DIR = PROJECT_ROOT / "data" / "chunk"
CHUNK_FILES = corpus_expectations.CHUNK_FILES
TREE_FILES = corpus_expectations.TREE_FILES
SOURCE_FILES = corpus_expectations.CHUNK_FILES + corpus_expectations.TREE_FILES
# Pinned known-good hashes. Without this anchor, a "before/after" comparison
# inside a single run cannot detect source files that were already corrupted —
# the comparison would trivially hold. Regenerate deliberately with
#   python scripts/verify_db.py --write-manifest
MANIFEST_PATH = CHUNK_DIR / "source_manifest.json"

# Counts are DERIVED from data/chunk/chunks_*.json, not hand-pinned literals.
# P-029 (2026-10-03): they used to live here as literals (NQCT=18, TOTAL=1307)
# and silently rotted the moment the internal regulation was enriched, breaking
# this script, embed_legal.py and verify_embeddings.py at once. Deriving them
# keeps every DB-vs-source assertion just as strict while removing the drift;
# the sha256 pins below are still what catch an unintended source edit.
EXPECTED_CHUNK_COUNTS = corpus_expectations.EXPECTED_CHUNK_COUNTS
EXPECTED_ARTICLE_COUNTS = corpus_expectations.EXPECTED_ARTICLE_COUNTS
EXPECTED_REF_COUNTS = corpus_expectations.EXPECTED_REF_COUNTS
TOTAL_CHUNKS = corpus_expectations.TOTAL_CHUNKS
TOTAL_REFS = corpus_expectations.TOTAL_REFS
EXPECTED_BOUNDARY = corpus_expectations.EXPECTED_BOUNDARY
EXPECTED_UNRESOLVED = corpus_expectations.EXPECTED_UNRESOLVED

INTERNAL_DOC_IDS = set(EXPECTED_CHUNK_COUNTS)
DOC_ID_TO_CODE = corpus_expectations.DOC_ID_TO_CODE
EXPECTED_DOC_COUNT = corpus_expectations.TOTAL_DOCS

EXTERNAL_LAW_ALLOWLIST: set[str] = {
    "Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng",
    "Luật An toàn, vệ sinh lao động",
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
}
LAW_NUMBER_RE = re.compile(r"^\d{2,3}/20\d{2}/[A-ZĐ0-9-]+$")

# V5-auto golden cases. Values are asserted literally in verify_v5_auto();
# anything that does not match is a FAIL, never a warning.
V5_CASES = {
    "V5.1_ND283_A044C01_to_BHXH_D28": "ND283_2026:CIII:M00:A044:C01",
    "V5.2_BLLD_D169_inbound_from_ND145": "BLLD:CXII:M00:A169:C01",
    "V5.3_A219C02_two_reference_directions": "BLLD:CXVII:M00:A219:C02",
    "V5.4_ND145_A070C03_to_BLLD_D122_HIGH": "ND145_2020:CVIII:M00:A070:C03",
    "V5.5_ND283_A066_LIST_self_D7_D14": "ND283_2026:CVI:M00:A066",
}

results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> bool:
    results.append((name, passed, detail))
    logger.info(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    return passed


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def all_source_chunks() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in CHUNK_FILES:
        out.extend(load_json(CHUNK_DIR / f))
    return out


# ---------------------------------------------------------------------------
# V1: connection + migration
# ---------------------------------------------------------------------------

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


def verify_v1(db: Session) -> None:
    logger.info("--- V1: connection + migration ---")
    try:
        db.execute(sa.text("SELECT 1"))
        record("V1.connection", True, "SELECT 1 ok")
    except Exception as exc:
        record("V1.connection", False, str(exc))
        return

    head = alembic_head()
    try:
        current = db.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
    except Exception as exc:
        record("V1.alembic_current_eq_head", False, f"alembic_version unreadable: {exc}")
        current = None
    record(
        "V1.alembic_current_eq_head",
        head is not None and current == head,
        f"current={current} head={head}",
    )

    for table in ("legal_documents", "legal_chunks", "legal_chunk_references"):
        exists = db.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=:t)"
            ),
            {"t": table},
        ).scalar()
        record(f"V1.table_{table}", bool(exists), f"exists={exists}")

    has_vector = db.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
    ).scalar()
    record("V1.vector_extension", bool(has_vector), f"exists={has_vector}")

    # NULLS NOT DISTINCT must actually be on the constraint (plan 3.4)
    cdef = db.execute(
        sa.text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='legal_chunk_references'::regclass AND conname='uq_legal_chunk_references'"
        )
    ).scalar()
    record(
        "V1.uq_nulls_not_distinct",
        bool(cdef) and "NULLS NOT DISTINCT" in cdef,
        f"{cdef}",
    )

    # the reverse traversal index must be NULLS NOT DISTINCT too (plan 3.4)
    ixdef = db.execute(
        sa.text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname='ix_legal_chunk_references_target_source'"
        )
    ).scalar()
    record(
        "V1.reverse_index_nulls_not_distinct",
        bool(ixdef)
        and "NULLS NOT DISTINCT" in ixdef
        and "target_chunk_id, source_chunk_id" in ixdef,
        f"{ixdef}",
    )

    # No redundant duplicate unique index on legal_documents.doc_code
    dup_uniques = db.execute(
        sa.text(
            "SELECT count(*) FROM pg_index i "
            "JOIN pg_class c ON c.oid=i.indexrelid "
            "WHERE i.indrelid='legal_documents'::regclass AND i.indisunique "
            "AND i.indpred IS NULL "
            "AND (SELECT array_agg(a.attname ORDER BY a.attname) "
            "     FROM unnest(i.indkey) k JOIN pg_attribute a "
            "       ON a.attrelid=i.indrelid AND a.attnum=k) = ARRAY['doc_code']::name[]"
        )
    ).scalar()
    record("V1.doc_code_single_unique", dup_uniques == 1, f"unique indexes={dup_uniques}")


# ---------------------------------------------------------------------------
# V2: legal_documents
# ---------------------------------------------------------------------------

def verify_v2(db: Session) -> None:
    logger.info("--- V2: legal_documents ---")
    doc_count = db.scalar(sa.select(sa.func.count()).select_from(LegalDocument))
    record("V2.doc_count", doc_count == EXPECTED_DOC_COUNT,
           f"count={doc_count} expected={EXPECTED_DOC_COUNT}")

    for doc_id, expected_art in EXPECTED_ARTICLE_COUNTS.items():
        doc = db.get(LegalDocument, doc_id)
        if doc is None:
            record(f"V2.{DOC_ID_TO_CODE[doc_id]}.exists", False, "missing")
            continue
        record(
            f"V2.{doc.doc_code}.article_count",
            doc.article_count == expected_art,
            f"expected={expected_art} got={doc.article_count}",
        )
        real_chunks = db.scalar(
            sa.select(sa.func.count()).select_from(LegalChunk).where(
                LegalChunk.document_id == doc_id
            )
        )
        record(
            f"V2.{doc.doc_code}.chunk_count_cross",
            doc.chunk_count == real_chunks,
            f"expected={real_chunks} got={doc.chunk_count}",
        )
        real_articles = db.scalar(
            sa.select(sa.func.count(sa.distinct(LegalChunk.article_number)))
            .select_from(LegalChunk)
            .where(LegalChunk.document_id == doc_id)
        )
        record(
            f"V2.{doc.doc_code}.article_count_cross",
            doc.article_count == real_articles,
            f"expected={real_articles} got={doc.article_count}",
        )

    blld = db.get(LegalDocument, "18/VBHN-VPQH")
    record(
        "V2.BLLD.status",
        blld is not None and blld.status == DOC_STATUS_PARTIALLY_AMENDED,
        f"status={blld.status if blld else 'N/A'}",
    )
    record(
        "V2.BLLD.amended_by_non_null",
        blld is not None and blld.amended_by is not None,
        f"keys={sorted((blld.amended_by or {}).keys()) if blld and blld.amended_by else None}",
    )
    # amended_by must be a REAL SQL NULL where there is nothing to record.
    # JSONB's default type would store a JSON 'null' instead, which
    # `amended_by IS NULL` would not match — so ask the database, not the ORM.
    json_null_docs = [
        row[0]
        for row in db.execute(
            sa.text(
                "SELECT doc_code FROM legal_documents "
                "WHERE amended_by IS NOT NULL AND jsonb_typeof(amended_by) <> 'object' "
                "ORDER BY doc_code"
            )
        )
    ]
    record(
        "V2.amended_by_is_object_or_null",
        not json_null_docs,
        f"non-object amended_by={json_null_docs}",
    )
    for doc_id in ("145/2020/NĐ-CP", "283/2026/NĐ-CP"):
        code = DOC_ID_TO_CODE[doc_id]
        is_sql_null = db.scalar(
            sa.text("SELECT amended_by IS NULL FROM legal_documents WHERE document_id = :d"),
            {"d": doc_id},
        )
        record(f"V2.{code}.amended_by_sql_null", bool(is_sql_null), f"IS NULL={is_sql_null}")
    for doc_id in ("145/2020/NĐ-CP", "283/2026/NĐ-CP"):
        d = db.get(LegalDocument, doc_id)
        record(
            f"V2.{DOC_ID_TO_CODE[doc_id]}.status",
            d is not None and d.status == DOC_STATUS_ACTIVE,
            f"status={d.status if d else 'N/A'}",
        )


# ---------------------------------------------------------------------------
# V3: legal_chunks
# ---------------------------------------------------------------------------

def verify_v3(db: Session) -> None:
    logger.info("--- V3: legal_chunks ---")
    for doc_id, expected in EXPECTED_CHUNK_COUNTS.items():
        count = db.scalar(
            sa.select(sa.func.count()).select_from(LegalChunk).where(
                LegalChunk.document_id == doc_id
            )
        )
        record(
            f"V3.{DOC_ID_TO_CODE[doc_id]}.count",
            count == expected,
            f"expected={expected} got={count}",
        )

    total = db.scalar(sa.select(sa.func.count()).select_from(LegalChunk))
    record("V3.total", total == TOTAL_CHUNKS, f"expected={TOTAL_CHUNKS} got={total}")

    empty = db.scalar(
        sa.select(sa.func.count()).select_from(LegalChunk).where(
            sa.or_(LegalChunk.text == "", sa.func.length(LegalChunk.text) == 0)
        )
    )
    record("V3.empty_text", empty == 0, f"empty={empty}")

    dups = db.execute(
        sa.select(LegalChunk.chunk_id)
        .group_by(LegalChunk.chunk_id)
        .having(sa.func.count() > 1)
    ).fetchall()
    record("V3.dup_chunk_id", not dups, f"dups={len(dups)}")

    # article coverage vs document_tree (and no extra articles)
    for doc_id, code in DOC_ID_TO_CODE.items():
        tree = load_json(CHUNK_DIR / f"document_tree_{code}.json")
        tree_articles: set[int] = set()
        for ch in tree.get("chapters", []):
            for a in ch.get("articles", []):
                tree_articles.add(a["number"])
            for sec in ch.get("sections", []):
                for a in sec.get("articles", []):
                    tree_articles.add(a["number"])
        db_articles = set(
            db.execute(
                sa.select(LegalChunk.article_number)
                .where(LegalChunk.document_id == doc_id)
                .distinct()
            ).scalars()
        )
        record(
            f"V3.{code}.article_coverage",
            tree_articles == db_articles,
            f"missing={sorted(tree_articles - db_articles)} "
            f"extra={sorted(db_articles - tree_articles)}",
        )


# ---------------------------------------------------------------------------
# V3-bis: special columns
# ---------------------------------------------------------------------------

def verify_v3_bis(db: Session) -> None:
    logger.info("--- V3-bis: special columns (seed=42, 30 ids) ---")
    by_id = {c["chunk_id"]: c for c in all_source_chunks()}
    rng = random.Random(42)
    all_ids = sorted(by_id)
    sample = rng.sample(all_ids, min(30, len(all_ids)))
    logger.info(f"  sampled {len(sample)} ids (seed=42), full list for reproduction:")
    for i, cid in enumerate(sample, 1):
        logger.info(f"    {i:2d}. {cid}")

    meta_fields = [
        "penalty_min_vnd",
        "penalty_max_vnd",
        "penalty_subject",
        "anomaly_flags",
        "has_chapeau",
        "chapeau_text",
        "is_quoted_external_text",
        "clause_number_is_implicit",
    ]
    mismatches: list[str] = []
    for cid in sample:
        src = by_id[cid]["metadata"]
        row = db.get(LegalChunk, cid)
        if row is None:
            mismatches.append(f"{cid}: absent from DB")
            continue
        for f in meta_fields:
            if src.get(f) != row.meta.get(f):
                mismatches.append(
                    f"{cid}.{f}: json={src.get(f)!r} db={row.meta.get(f)!r}"
                )
        if src.get("clause_number") != row.clause_number:
            mismatches.append(
                f"{cid}.clause_number: json={src.get('clause_number')!r} "
                f"db={row.clause_number!r}"
            )
    for m in mismatches:
        logger.error(f"    {m}")
    record("V3-bis.special_columns", not mismatches, f"mismatches={len(mismatches)}")

    # plan: BLLD Dieu 219 must have exactly 20 is_quoted_external_text = True
    n_quoted = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunk)
        .where(LegalChunk.meta["is_quoted_external_text"].astext == "true")
    )
    record("V3-bis.quoted_external_count", n_quoted == 20, f"true={n_quoted} (expected 20)")


# ---------------------------------------------------------------------------
# V3-ter: dangling parent
# ---------------------------------------------------------------------------

def verify_v3_ter(db: Session) -> None:
    logger.info("--- V3-ter: dangling parent ---")
    db_dangling = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunk)
        .where(
            LegalChunk.parent_chunk_id.is_not(None),
            LegalChunk.parent_chunk_id.not_in(sa.select(LegalChunk.chunk_id)),
        )
    )
    legal_chunks = all_source_chunks()
    ids = {c["chunk_id"] for c in legal_chunks}
    json_dangling = sum(
        1 for c in legal_chunks if c.get("parent_chunk_id") and c["parent_chunk_id"] not in ids
    )
    logger.info(f"  DB={db_dangling}  JSON={json_dangling}")
    record(
        "V3-ter.dangling_parent",
        db_dangling == json_dangling,
        f"db={db_dangling} json={json_dangling}",
    )


# ---------------------------------------------------------------------------
# V4: references
# ---------------------------------------------------------------------------

def verify_v4(db: Session) -> None:
    logger.info("--- V4: references ---")
    total = db.scalar(sa.select(sa.func.count()).select_from(LegalChunkReference))
    record("V4.total", total == TOTAL_REFS, f"expected={TOTAL_REFS} got={total}")

    for doc_id, expected in EXPECTED_REF_COUNTS.items():
        count = db.scalar(
            sa.select(sa.func.count())
            .select_from(LegalChunkReference)
            .join(LegalChunk, LegalChunkReference.source_chunk_id == LegalChunk.chunk_id)
            .where(LegalChunk.document_id == doc_id)
        )
        record(
            f"V4.{DOC_ID_TO_CODE[doc_id]}.count",
            count == expected,
            f"expected={expected} got={count}",
        )

    invalid = sorted(
        td
        for td in db.execute(sa.select(LegalChunkReference.target_doc).distinct()).scalars()
        if td not in INTERNAL_DOC_IDS
        and td not in EXTERNAL_LAW_ALLOWLIST
        and not LAW_NUMBER_RE.match(td)
    )
    record("V4.target_doc_valid", not invalid, f"invalid={invalid}")

    # every internal ref must point at an article that exists
    # P-029 FIX 2026-10-01: them NQCT (self-ref NOI_QUY phai duoc kiem tra).
    missing = db.execute(
        sa.text(
            """
            SELECT r.source_chunk_id, r.target_doc, r.article
            FROM legal_chunk_references r
            WHERE r.target_doc IN ('18/VBHN-VPQH','145/2020/NĐ-CP','283/2026/NĐ-CP','NQLD-HRCORP-2026')
              AND NOT EXISTS (
                SELECT 1 FROM legal_chunks t
                WHERE t.document_id = r.target_doc AND t.article_number = r.article)
            """
        )
    ).fetchall()
    record("V4.internal_article_exists", not missing, f"missing={len(missing)}")

    # needs_review must agree with needs_reason (single source of truth)
    inconsistent = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunkReference)
        .where(
            sa.or_(
                sa.and_(
                    LegalChunkReference.needs_reason.is_(None),
                    LegalChunkReference.needs_review.is_(True),
                ),
                sa.and_(
                    LegalChunkReference.needs_reason.is_not(None),
                    LegalChunkReference.needs_review.is_(False),
                ),
            )
        )
    )
    record("V4.needs_review_consistent", inconsistent == 0, f"inconsistent={inconsistent}")


# ---------------------------------------------------------------------------
# V4-bis / V4-ter
# ---------------------------------------------------------------------------

def verify_v4_bis(db: Session) -> None:
    logger.info("--- V4-bis: UNRESOLVED ---")
    n = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunkReference)
        .where(LegalChunkReference.needs_reason == "UNRESOLVED")
    )
    record("V4-bis.unresolved", n == EXPECTED_UNRESOLVED, f"expected=0 got={n}")


def verify_v4_ter(db: Session) -> None:
    logger.info("--- V4-ter: needs_review aggregate ---")
    boundary = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunkReference)
        .where(LegalChunkReference.needs_reason == "BOUNDARY")
    )
    record(
        "V4-ter.boundary",
        boundary == EXPECTED_BOUNDARY,
        f"expected={EXPECTED_BOUNDARY} got={boundary}",
    )
    unresolved = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunkReference)
        .where(LegalChunkReference.needs_reason == "UNRESOLVED")
    )
    record("V4-ter.unresolved", unresolved == 0, f"got={unresolved}")
    total_flagged = db.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunkReference)
        .where(LegalChunkReference.needs_review.is_(True))
    )
    record(
        "V4-ter.total_flagged",
        total_flagged == EXPECTED_BOUNDARY + EXPECTED_UNRESOLVED,
        f"got={total_flagged}",
    )


# ---------------------------------------------------------------------------
# V5-auto: fixed traversal, hard assertions
# ---------------------------------------------------------------------------

def verify_v5_auto(db: Session) -> None:
    logger.info("--- V5-auto: fixed traversal cases ---")
    for name in V5_CASES:
        logger.info(f"  case {name}")

    # Case 1: ND283 A044:C01 -> BHXH D28, target_chunk_id must be NULL
    rows = db.execute(
        sa.select(LegalChunkReference)
        .where(
            LegalChunkReference.source_chunk_id == V5_CASES["V5.1_ND283_A044C01_to_BHXH_D28"],
            LegalChunkReference.target_doc == "Luật Bảo hiểm xã hội",
            LegalChunkReference.article == 28,
        )
    ).scalars().all()
    ok = len(rows) == 1 and rows[0].target_chunk_id is None
    record(
        "V5.1_ND283_A044C01_to_BHXH_D28",
        ok,
        f"rows={len(rows)} target_chunk_id={rows[0].target_chunk_id if rows else 'N/A'} "
        f"(expect 1 row, NULL target)",
    )

    # Case 2: BLLD D169 has inbound from ND145 (exactly 2 sources)
    inbound = (
        db.execute(
            sa.select(LegalChunkReference.source_chunk_id)
            .join(LegalChunk, LegalChunkReference.source_chunk_id == LegalChunk.chunk_id)
            .where(
                LegalChunk.document_id == "145/2020/NĐ-CP",
                LegalChunkReference.target_doc == "18/VBHN-VPQH",
                LegalChunkReference.article == 169,
            )
        )
        .scalars()
        .all()
    )
    expected_inbound = {"ND145_2020:CIII:M02:A008:C01", "ND145_2020:CX:M00:A089:C01:P-d1"}
    record(
        "V5.2_BLLD_D169_inbound_from_ND145",
        set(inbound) == expected_inbound,
        f"inbound={sorted(inbound)}",
    )

    # Case 3: A219:C02 references TWO directions — an external law (BHXH) and
    # an internal doc (BLLD D169). NOTE: there is NO inbound edge to D219 in
    # this dataset, so "2 chiều" is read as "2 reference directions", matching
    # data/chunk/CHANGELOG.md item 1. The reverse-direction check below
    # therefore asserts multi-source reachability of the D169 targets, which
    # is what ix_legal_chunk_references_target_source exists for.
    a219 = V5_CASES["V5.3_A219C02_two_reference_directions"]
    r219 = (
        db.execute(
            sa.select(LegalChunkReference).where(LegalChunkReference.source_chunk_id == a219)
        )
        .scalars()
        .all()
    )
    to_bhxh = [r for r in r219 if r.target_doc == "Luật Bảo hiểm xã hội"]
    record(
        "V5.3_A219C02_quoted_external",
        len(to_bhxh) == 1
        and to_bhxh[0].target_chunk_id is None
        and to_bhxh[0].article == 2
        and to_bhxh[0].clause == 1
        and to_bhxh[0].point == "e"
        and to_bhxh[0].rule == "QUOTED_EXTERNAL",
        f"bhxh_refs={len(to_bhxh)} "
        f"art={to_bhxh[0].article if to_bhxh else 'N/A'} "
        f"cl={to_bhxh[0].clause if to_bhxh else 'N/A'} "
        f"pt={to_bhxh[0].point if to_bhxh else 'N/A'} "
        f"target={to_bhxh[0].target_chunk_id if to_bhxh else 'N/A'} "
        f"(expect 1: BHXH D2 cl1 pte, target NULL)",
    )
    to_169 = [r for r in r219 if r.target_doc == "18/VBHN-VPQH" and r.article == 169]
    tgt_169 = sorted(r.target_chunk_id for r in to_169)
    record(
        "V5.3_A219C02_to_D169",
        len(to_169) == 2
        and {r.clause for r in to_169} == {2, 3}
        and all(r.target_chunk_id is not None for r in to_169)
        and tgt_169 == ["BLLD:CXII:M00:A169:C02", "BLLD:CXII:M00:A169:C03"],
        f"refs={len(to_169)} clauses={sorted(r.clause for r in to_169)} targets={tgt_169}",
    )
    # reverse direction: each D169 target is reachable from >= 2 distinct sources
    for tgt in ("BLLD:CXII:M00:A169:C02", "BLLD:CXII:M00:A169:C03"):
        srcs = (
            db.execute(
                sa.select(sa.distinct(LegalChunkReference.source_chunk_id)).where(
                    LegalChunkReference.target_chunk_id == tgt
                )
            )
            .scalars()
            .all()
        )
        record(
            f"V5.3_reverse_inbound_{tgt}",
            len(srcs) >= 2,
            f"distinct_sources={len(srcs)} (expect >=2, exercises reverse index)",
        )

    # Case 4: ND145 A070:C03 -> BLLD D122 HIGH.
    # The ref carries point 'c', but BLLD D122 only has CLAUSE legal_chunks (C01-C06),
    # so resolution deterministically falls back to clause 1. Pinned exactly so
    # any change in fallback behaviour is caught.
    r4 = (
        db.execute(
            sa.select(LegalChunkReference).where(
                LegalChunkReference.source_chunk_id
                == V5_CASES["V5.4_ND145_A070C03_to_BLLD_D122_HIGH"],
                LegalChunkReference.target_doc == "18/VBHN-VPQH",
                LegalChunkReference.article == 122,
                LegalChunkReference.confidence == "HIGH",
            )
        )
        .scalars()
        .all()
    )
    tgt_level = (
        db.scalar(
            sa.select(LegalChunk.chunk_level).where(
                LegalChunk.chunk_id == "BLLD:CVIII:M01:A122:C01"
            )
        )
        if r4
        else None
    )
    record(
        "V5.4_ND145_A070C03_to_BLLD_D122_HIGH",
        len(r4) == 1
        and r4[0].target_chunk_id == "BLLD:CVIII:M01:A122:C01"
        and tgt_level == "CLAUSE"
        and r4[0].clause == 1
        and r4[0].point == "c",
        f"rows={len(r4)} "
        f"target={r4[0].target_chunk_id if r4 else 'N/A'} level={tgt_level} "
        f"cl={r4[0].clause if r4 else 'N/A'} pt={r4[0].point if r4 else 'N/A'} "
        f"(expect 1 -> BLLD:CVIII:M01:A122:C01 CLAUSE, fallback from missing point)",
    )

    # Case 5: ND283 A066 LIST_EXPANSION self -> D7 and D14
    r5 = (
        db.execute(
            sa.select(LegalChunkReference).where(
                LegalChunkReference.source_chunk_id == V5_CASES["V5.5_ND283_A066_LIST_self_D7_D14"],
                LegalChunkReference.rule == "LIST_EXPANSION",
                LegalChunkReference.target_doc == "283/2026/NĐ-CP",
            )
        )
        .scalars()
        .all()
    )
    arts = sorted(r.article for r in r5)
    record(
        "V5.5_ND283_A066_LIST_self_D7_D14",
        arts == [7, 14] and all(r.target_chunk_id is not None for r in r5),
        f"articles={arts} targets={[r.target_chunk_id for r in r5]} (expect [7, 14], non-null)",
    )


# ---------------------------------------------------------------------------
# V6: idempotent (runs the real CLI)
# ---------------------------------------------------------------------------

def verify_v6() -> None:
    logger.info("--- V6: idempotent (re-running real CLI) ---")

    def fingerprint() -> tuple[dict, str | None]:
        with SessionLocal() as s:
            counts = {
                t: s.scalar(sa.select(sa.func.count()).select_from(t))
                for t in (LegalDocument, LegalChunk, LegalChunkReference)
            }
            # Content fingerprint, deliberately NOT keyed on ref_id: B5 reseeds
            # with DELETE+INSERT so SERIAL ids shift, the data must not.
            fp = s.execute(
                sa.text(
                    "SELECT md5(string_agg(x, '|' ORDER BY x)) FROM ("
                    "  SELECT source_chunk_id||coalesce(target_chunk_id,'~')||target_doc"
                    "         ||article::text||coalesce(clause::text,'~')"
                    "         ||coalesce(point,'~')||rule||confidence"
                    "         ||needs_review::text||coalesce(needs_reason,'~') AS x"
                    "  FROM legal_chunk_references) s"
                )
            ).scalar()
            return counts, fp

    before, fp_before = fingerprint()

    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "seed_legal.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    record("V6.rerun_exit_zero", proc.returncode == 0, f"returncode={proc.returncode}")
    if proc.returncode != 0:
        logger.error(proc.stdout[-2000:])
        logger.error(proc.stderr[-2000:])
        return

    after, fp_after = fingerprint()
    for t, name in ((LegalDocument, "legal_documents"), (LegalChunk, "legal_chunks"), (LegalChunkReference, "refs")):
        record(
            f"V6.count_{name}",
            before[t] == after[t],
            f"before={before[t]} after={after[t]}",
        )
    record("V6.ref_fingerprint", fp_before == fp_after, f"{fp_before} == {fp_after}")

    with SessionLocal() as s:
        stale = s.scalar(
            sa.text(
                "SELECT count(*) FROM legal_chunk_references r "
                "WHERE NOT EXISTS (SELECT 1 FROM legal_chunks c WHERE c.chunk_id=r.source_chunk_id)"
            )
        )
    record("V6.no_orphan_refs", stale == 0, f"orphans={stale}")


# ---------------------------------------------------------------------------
# V7: source untouched
# ---------------------------------------------------------------------------

def snapshot_sources() -> dict[str, str]:
    return {
        f: sha256_file(CHUNK_DIR / f)
        for f in SOURCE_FILES
        if (CHUNK_DIR / f).exists()
    }


def load_manifest() -> dict[str, str] | None:
    if not MANIFEST_PATH.exists():
        return None
    try:
        return load_json(MANIFEST_PATH).get("files", {})
    except Exception:
        return None


def write_manifest(files: dict[str, str]) -> None:
    import datetime as _dt

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "pinned_at": _dt.datetime.now(_dt.UTC).isoformat(),
                "note": (
                    "Known-good sha256 of the frozen step3 outputs consumed by B4/B5. "
                    "Regenerate only after an intentional, reviewed source change: "
                    "python scripts/verify_db.py --write-manifest"
                ),
                "files": files,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    logger.info(f"  wrote manifest -> {MANIFEST_PATH}")


def verify_v7(before: dict[str, str], write_manifest_flag: bool) -> bool:
    """Two independent guarantees:
    1. every source file matches the pinned known-good manifest
       (catches corruption that happened before this run), and
    2. the seed step did not modify any source file (before vs after).
    """
    logger.info("--- V7: source untouched ---")
    missing = [f for f in SOURCE_FILES if not (CHUNK_DIR / f).exists()]
    record("V7.files_present", not missing, f"missing={missing}")

    now = snapshot_sources()
    for f, h in now.items():
        logger.info(f"  {f}: {h}")

    manifest = load_manifest()
    if write_manifest_flag:
        write_manifest(now)
        record("V7.manifest_written", True, f"{len(now)} files pinned")
    else:
        record(
            "V7.manifest_exists",
            manifest is not None,
            f"{MANIFEST_PATH.name} present" if manifest else "MISSING — run with --write-manifest",
        )
        if manifest is not None:
            drifted = sorted(
                f
                for f, h in manifest.items()
                if now.get(f) != h
            )
            absent = sorted(set(manifest) - set(now))
            for f, h in manifest.items():
                mark = "OK  " if now.get(f) == h else "DIFF"
                logger.info(f"  [{mark}] {f}: {h[:16]}…")
            record(
                "V7.matches_pinned_manifest",
                not drifted and not absent,
                f"drifted={drifted} absent={absent}",
            )

    changed = sorted(f for f, h in before.items() if now.get(f) != h)
    record("V7.seed_did_not_modify_sources", not changed, f"changed={changed}")

    for f in CHUNK_FILES:
        try:
            n = len(load_json(CHUNK_DIR / f))
            record(f"V7.parse_{f}", n > 0, f"legal_chunks={n}")
        except Exception as exc:
            record(f"V7.parse_{f}", False, str(exc))
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    results.clear()
    write_manifest_flag = "--write-manifest" in sys.argv
    logger.info("Starting verify_db.py")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    if write_manifest_flag:
        logger.info("MODE: --write-manifest (re-pinning source hashes)")

    # snapshot BEFORE anything, so V7 can prove the seed did not touch sources
    before = snapshot_sources()

    db: Session = SessionLocal()
    try:
        verify_v1(db)
        verify_v2(db)
        verify_v3(db)
        verify_v3_bis(db)
        verify_v3_ter(db)
        verify_v4(db)
        verify_v4_bis(db)
        verify_v4_ter(db)
        verify_v5_auto(db)
    finally:
        db.close()

    verify_v6()                                # re-seeds via the real CLI
    verify_v7(before, write_manifest_flag)     # manifest + before/after

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
