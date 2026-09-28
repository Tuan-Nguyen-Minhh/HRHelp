"""Seed B4 (legal_documents + legal_chunks) and B5 (legal_chunk_references) from data/chunk/*.json.

B4: Upsert legal_documents, bulk insert legal_chunks, compute chunk_count/article_count.
    One transaction per chunk-file (plan 2.3).
B5: DELETE all legal_chunk_references then bulk insert resolved refs, ONE transaction
    (plan 3.6 — crash mid-way rolls back, no half-seeded state).

Idempotent: safe to run any number of times.

Resolution policy (plan 3.5), deterministic and level-correct:
    POINT matches letter  ->  CLAUSE matches number  ->  ARTICLE representative
A ref whose requested granularity has no matching chunk falls back to the
article's *representative* chunk (ARTICLE chunk if present, else the lowest
clause_number chunk). The fallback is deterministic and recorded in the seed
log; `legal_chunk_references` has no granularity column by plan design, so the
logical reference always stays readable via target_doc/article/clause/point.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402
from src.models.legal import (  # noqa: E402
    DOC_STATUS_ACTIVE,
    DOC_STATUS_PARTIALLY_AMENDED,
    LEVEL_ARTICLE,
    LEVEL_CLAUSE,
    LEVEL_POINT,
    NEEDS_REASON_BOUNDARY,
    NEEDS_REASON_UNRESOLVED,
    LegalChunk,
    LegalChunkReference,
    LegalDocument,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_legal")

_sync_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(
    bind=_sync_engine, autoflush=False, expire_on_commit=False
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNK_DIR = PROJECT_ROOT / "data" / "chunk"

DOCUMENTS: list[dict[str, Any]] = [
    {
        "document_id": "18/VBHN-VPQH",
        "doc_code": "BLLD",
        "document_type": "BO_LUAT",
        "document_form": "VAN_BAN_HOP_NHAT",
        "title": "Bộ luật Lao động",
        "status": DOC_STATUS_PARTIALLY_AMENDED,
    },
    {
        "document_id": "145/2020/NĐ-CP",
        "doc_code": "ND145_2020",
        "document_type": "NGHI_DINH",
        "document_form": "VAN_BAN_GOC",
        "title": "Nghị định 145/2020/NĐ-CP",
        "status": DOC_STATUS_ACTIVE,
    },
    {
        "document_id": "283/2026/NĐ-CP",
        "doc_code": "ND283_2026",
        "document_type": "NGHI_DINH",
        "document_form": "VAN_BAN_GOC",
        "title": "Nghị định 283/2026/NĐ-CP",
        "status": DOC_STATUS_ACTIVE,
    },
]

INTERNAL_DOC_IDS: set[str] = {d["document_id"] for d in DOCUMENTS}

# External law allowlist — mirrors KNOWN_LAW_PREFIXES in step3
# cross_reference_resolver.py. Anything outside this set + the law-number
# regex becomes UNRESOLVED (needs_review=true).
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

CHUNK_FILES = [
    "chunks_BLLD.json",
    "chunks_ND145_2020.json",
    "chunks_ND283_2026.json",
]

BATCH_SIZE = 500

# Keys promoted to dedicated indexed columns (everything else lands in meta)
SEPARATE_COLUMN_KEYS = frozenset(
    {
        "document_id",
        "document_type",
        "document_form",
        "article_number",
        "clause_number",
        "point_letter",
        "chunk_level",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_law_number(target_doc: str) -> bool:
    """target_doc is a law number like '124/2025/QH15'."""
    return bool(LAW_NUMBER_RE.match(target_doc))


def is_external_allowlisted(target_doc: str) -> bool:
    return target_doc in EXTERNAL_LAW_ALLOWLIST or is_law_number(target_doc)


def build_meta(chunk_data: dict[str, Any]) -> dict[str, Any]:
    """Everything that is not a dedicated column goes into meta JSONB."""
    meta = chunk_data.get("metadata", {})
    return {k: v for k, v in meta.items() if k not in SEPARATE_COLUMN_KEYS}


class ChunkIndex:
    """Level-aware, deterministic index for resolving target_chunk_id.

    The first implementation used one flat dict and wrote EVERY chunk into both
    the 2-term and the 3-term key:

        lookup[(doc, article)]        = cid   # for every chunk
        lookup[(doc, article, clause)] = cid  # for every chunk with a clause

    so trailing CLAUSE/POINT legal_chunks silently overwrote the ARTICLE entry. That
    left 144/403 ARTICLE keys and 66/691 CLAUSE keys pointing at the wrong
    level, and put 105/565 stored refs (18.6%) on an arbitrary sibling clause or
    point. Each level now has its own namespace and the article representative
    is picked explicitly instead of by overwrite order.
    """

    def __init__(self, legal_chunks: list[dict[str, Any]]) -> None:
        self.by_clause: dict[tuple, str] = {}
        self.by_point: dict[tuple, str] = {}
        # (doc, article) -> (level_rank, clause_number, point, chunk_id)
        article_candidates: dict[tuple, list[tuple]] = {}

        for c in legal_chunks:
            m = c["metadata"]
            doc = m["document_id"]
            art = m["article_number"]
            cl = m.get("clause_number")
            pt = m.get("point_letter")
            level = m["chunk_level"]
            cid = c["chunk_id"]

            if level == LEVEL_CLAUSE and cl is not None:
                self.by_clause[(doc, art, cl)] = cid
            elif level == LEVEL_POINT and cl is not None and pt is not None:
                self.by_point[(doc, art, cl, pt.lower())] = cid

            rank = {LEVEL_ARTICLE: 0, LEVEL_CLAUSE: 1, LEVEL_POINT: 2}[level]
            article_candidates.setdefault((doc, art), []).append(
                (rank, cl if cl is not None else -1, pt or "", cid)
            )

        # ARTICLE chunk wins; otherwise lowest clause_number; then lowest point
        self.article_rep: dict[tuple, str] = {
            k: min(v)[3] for k, v in article_candidates.items()
        }

    def __len__(self) -> int:
        return len(self.article_rep) + len(self.by_clause) + len(self.by_point)

    def resolve(
        self,
        target_doc: str,
        article: int,
        clause: int | None,
        point: str | None,
    ) -> tuple[str | None, str]:
        """Return (target_chunk_id, how). `how` is for the seed log only."""
        if target_doc not in INTERNAL_DOC_IDS:
            return None, "external"

        if point is not None and clause is not None:
            hit = self.by_point.get((target_doc, article, clause, point.lower()))
            if hit:
                return hit, "point"
        if clause is not None:
            hit = self.by_clause.get((target_doc, article, clause))
            if hit:
                return hit, "clause"
        hit = self.article_rep.get((target_doc, article))
        if hit:
            how = "article" if clause is None and point is None else "fallback"
            return hit, how
        return None, "no_article"


# ---------------------------------------------------------------------------
# B4: Documents + Chunks
# ---------------------------------------------------------------------------

def _chunk_row(c: dict[str, Any]) -> dict[str, Any]:
    m = c["metadata"]
    return {
        "chunk_id": c["chunk_id"],
        "document_id": m["document_id"],
        "parent_chunk_id": c.get("parent_chunk_id"),
        "header_context": c.get("header_context"),
        "text": c["text"],
        "article_number": m["article_number"],
        "clause_number": m.get("clause_number"),
        "point_letter": m.get("point_letter"),
        "chunk_level": m["chunk_level"],
        "meta": build_meta(c),
    }


def seed_documents(db: Session) -> None:
    for d in DOCUMENTS:
        stmt = pg_insert(LegalDocument).values(
            document_id=d["document_id"],
            doc_code=d["doc_code"],
            document_type=d["document_type"],
            document_form=d["document_form"],
            title=d["title"],
            status=d["status"],
            # amended_by deliberately omitted: the column then stays SQL NULL
            # (passing None would land as JSON 'null' inside JSONB)
            article_count=0,  # recomputed from real rows at the end of B4
            chunk_count=0,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["document_id"],
            set_={
                "doc_code": stmt.excluded.doc_code,
                "document_type": stmt.excluded.document_type,
                "document_form": stmt.excluded.document_form,
                "title": stmt.excluded.title,
                "status": stmt.excluded.status,
                "updated_at": sa.func.now(),
            },
        )
        db.execute(stmt)
    db.flush()

    for d in DOCUMENTS:
        tree_path = CHUNK_DIR / f"document_tree_{d['doc_code']}.json"
        footnotes = load_json(tree_path).get("footnotes", {}) if tree_path.exists() else {}
        # Always write, including the empty case, so a stale value from an
        # earlier seed cannot survive. With JSONB(none_as_null=True) the empty
        # case lands as a real SQL NULL rather than JSON 'null'.
        db.execute(
            sa.update(LegalDocument)
            .where(LegalDocument.document_id == d["document_id"])
            .values(amended_by=footnotes or None)
        )
        if footnotes:
            logger.info(
                f"  amended_by {d['doc_code']}: {len(footnotes)} footnotes"
            )
        else:
            logger.info(f"  amended_by {d['doc_code']}: SQL NULL (no footnotes)")


def seed_chunk_file(db: Session, fname: str) -> int:
    """Insert one chunk file inside the caller's transaction."""
    legal_chunks = load_json(CHUNK_DIR / fname)
    rows = [_chunk_row(c) for c in legal_chunks]
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        stmt = pg_insert(LegalChunk).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["chunk_id"],
            set_={
                "document_id": stmt.excluded.document_id,
                "parent_chunk_id": stmt.excluded.parent_chunk_id,
                "header_context": stmt.excluded.header_context,
                "text": stmt.excluded.text,
                "article_number": stmt.excluded.article_number,
                "clause_number": stmt.excluded.clause_number,
                "point_letter": stmt.excluded.point_letter,
                "chunk_level": stmt.excluded.chunk_level,
                "meta": stmt.excluded.meta,
                "updated_at": sa.func.now(),
            },
        )
        db.execute(stmt)
    return len(rows)


def recompute_counts(db: Session) -> None:
    """chunk_count / article_count from real rows — never hard-coded."""
    for d in DOCUMENTS:
        doc_id = d["document_id"]
        chunk_count = db.scalar(
            sa.select(sa.func.count()).select_from(LegalChunk).where(
                LegalChunk.document_id == doc_id
            )
        )
        article_count = db.scalar(
            sa.select(sa.func.count(sa.distinct(LegalChunk.article_number)))
            .select_from(LegalChunk)
            .where(LegalChunk.document_id == doc_id)
        )
        db.execute(
            sa.update(LegalDocument)
            .where(LegalDocument.document_id == doc_id)
            .values(
                chunk_count=chunk_count,
                article_count=article_count,
                updated_at=sa.func.now(),
            )
        )
        logger.info(
            f"  {d['doc_code']}: chunk_count={chunk_count} "
            f"article_count={article_count} (from real rows)"
        )


def seed_b4(db: Session) -> None:
    """Documents + legal_chunks. One transaction per chunk-file, then a final one."""
    logger.info("=== B4: legal_documents + legal_chunks ===")
    seed_documents(db)
    db.commit()
    logger.info(f"  upserted {len(DOCUMENTS)} legal_documents")

    total = 0
    for fname in CHUNK_FILES:
        # plan: transaction per chunk-file
        with db.begin():
            n = seed_chunk_file(db, fname)
        total += n
        logger.info(f"  {fname}: {n} legal_chunks committed")
    logger.info(f"  total legal_chunks: {total}")

    recompute_counts(db)
    db.commit()
    logger.info("=== B4 complete ===")


# ---------------------------------------------------------------------------
# B5: LegalChunk References
# ---------------------------------------------------------------------------

def seed_b5(db: Session) -> None:
    """DELETE then bulk insert, in ONE transaction (plan 3.6)."""
    logger.info("=== B5: legal_chunk_references ===")

    all_chunks: list[dict[str, Any]] = []
    for fname in CHUNK_FILES:
        all_chunks.extend(load_json(CHUNK_DIR / fname))

    index = ChunkIndex(all_chunks)
    logger.info(f"  chunk index: {len(index)} entries")

    with db.begin():
        db.execute(sa.delete(LegalChunkReference))

        rows: list[dict[str, Any]] = []
        how_counter: Counter[str] = Counter()
        rule_counter: Counter[str] = Counter()
        fallback_samples: list[str] = []

        for c in all_chunks:
            source_chunk_id = c["chunk_id"]
            for r in c.get("references", []):
                target_doc = r["target_doc"]
                article = r["article"]
                clause = r.get("clause")
                point = r.get("point")
                confidence = r.get("confidence", "HIGH")
                rule = r.get("rule", "")

                target_chunk_id, how = index.resolve(
                    target_doc, article, clause, point
                )
                how_counter[how] += 1
                rule_counter[rule] += 1

                # needs_reason has exactly two legal values (DB CHECK).
                # UNRESOLVED wins over BOUNDARY when both would apply.
                if target_doc not in INTERNAL_DOC_IDS and not is_external_allowlisted(
                    target_doc
                ):
                    needs_reason = NEEDS_REASON_UNRESOLVED
                elif rule == "BOUNDARY_CHECK" or confidence == "LOW":
                    needs_reason = NEEDS_REASON_BOUNDARY
                else:
                    needs_reason = None

                if how == "fallback" and len(fallback_samples) < 15:
                    fallback_samples.append(
                        f"{source_chunk_id} -> {target_doc} D{article} "
                        f"cl={clause} pt={point} => {target_chunk_id}"
                    )

                rows.append(
                    {
                        "source_chunk_id": source_chunk_id,
                        "target_chunk_id": target_chunk_id,
                        "target_doc": target_doc,
                        "article": article,
                        "clause": clause,
                        "point": point,
                        "rule": rule,
                        "confidence": confidence,
                        # single source of truth: needs_review == needs_reason
                        "needs_review": needs_reason is not None,
                        "needs_reason": needs_reason,
                    }
                )

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            stmt = pg_insert(LegalChunkReference).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_legal_chunk_references",
                set_={
                    "target_chunk_id": stmt.excluded.target_chunk_id,
                    "confidence": stmt.excluded.confidence,
                    "needs_review": stmt.excluded.needs_review,
                    "needs_reason": stmt.excluded.needs_reason,
                    "updated_at": sa.func.now(),
                },
            )
            db.execute(stmt)

    logger.info(f"  refs inserted: {len(rows)}")
    logger.info(f"  resolution: {dict(how_counter)}")
    logger.info(
        "  needs_review: "
        f"BOUNDARY={sum(1 for r in rows if r['needs_reason'] == NEEDS_REASON_BOUNDARY)} "
        f"UNRESOLVED={sum(1 for r in rows if r['needs_reason'] == NEEDS_REASON_UNRESOLVED)}"
    )
    logger.info(f"  by rule: {dict(rule_counter)}")
    if fallback_samples:
        logger.info(
            f"  representative-fallback samples ({how_counter['fallback']} total):"
        )
        for s in fallback_samples:
            logger.info(f"    {s}")
    logger.info("=== B5 complete ===")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Starting seed_legal.py")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    db: Session = SessionLocal()
    try:
        seed_b4(db)
        seed_b5(db)
        logger.info("Seed complete!")
    except Exception:
        db.rollback()
        logger.exception("Seed failed — rolled back")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
