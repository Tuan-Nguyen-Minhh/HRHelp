"""Copy the cross-reference graph from legal_chunk_references to chunk_references.

One-time ETL, same shape as ``seed_hr_from_legal.py``: read the build-time
table, map the semantic chunk ids onto the HR-side UUIDs, write the result in a
single transaction.

The join key is ``document_chunks.chunk_metadata->>'legal_chunk_id'``, which
``seed_hr_from_legal.py`` already writes. No new column and no index are needed
for it: this runs once over 1377 rows, so a single SELECT builds the whole map
in memory.

Idempotent: the table is emptied before the insert, so re-running after
``seed_hr_from_legal.py`` regenerates the graph against the new UUIDs instead of
pointing at ids that no longer exist.

Run:
    python -m scripts.copy_chunk_references
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402
from src.models.chunk_references import ChunkReference  # noqa: E402
from src.models.document_chunks import DocumentChunk  # noqa: E402
from src.models.legal import LegalChunkReference  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("copy_chunk_references")

BATCH_SIZE = 200

_sync_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(bind=_sync_engine, autoflush=False, expire_on_commit=False)


def semantic_to_uuid(session: Session) -> dict[str, Any]:
    """Map semantic chunk id -> document_chunks.id, in one query."""
    rows = session.execute(
        sa.select(DocumentChunk.id, DocumentChunk.chunk_metadata["legal_chunk_id"].astext).where(
            DocumentChunk.chunk_metadata["legal_chunk_id"].astext.is_not(None)
        )
    ).all()
    mapping = {semantic: uuid for uuid, semantic in rows if semantic}
    logger.info("  mapped %d document_chunks that carry a legal_chunk_id", len(mapping))
    return mapping


def copy_references(session: Session) -> dict[str, int]:
    """Empty chunk_references and refill it from the source table."""
    mapping = semantic_to_uuid(session)

    sources = session.execute(
        sa.select(
            LegalChunkReference.source_chunk_id,
            LegalChunkReference.target_chunk_id,
            LegalChunkReference.target_doc,
            LegalChunkReference.article,
            LegalChunkReference.clause,
            LegalChunkReference.point,
            LegalChunkReference.rule,
            LegalChunkReference.confidence,
            LegalChunkReference.needs_review,
            LegalChunkReference.needs_reason,
        )
    ).all()
    logger.info("  source table holds %d references", len(sources))

    rows: list[dict[str, Any]] = []
    missing_source: set[str] = set()
    missing_target: set[str] = set()
    for src, tgt, doc, art, cl, pt, rule, conf, review, reason in sources:
        source_uuid = mapping.get(src)
        if source_uuid is None:
            missing_source.add(src)
            continue
        target_uuid = None
        if tgt is not None:
            target_uuid = mapping.get(tgt)
            if target_uuid is None:
                # A target that is not in the corpus behaves exactly like an
                # external citation: keep the edge, drop the FK.
                missing_target.add(tgt)
        rows.append(
            {
                "source_chunk_id": source_uuid,
                "target_chunk_id": target_uuid,
                "target_doc": doc,
                "article": art,
                "clause": cl,
                "point": pt,
                "rule": rule,
                "confidence": conf,
                "needs_review": bool(review),
                "needs_reason": reason,
            }
        )

    if missing_source:
        logger.error("  %d source chunks are absent from document_chunks", len(missing_source))
        for item in sorted(missing_source)[:10]:
            logger.error("    missing source: %s", item)
    if missing_target:
        logger.warning(
            "  %d targets are absent from document_chunks -> stored as external (NULL)",
            len(missing_target),
        )
        for item in sorted(missing_target)[:10]:
            logger.warning("    missing target: %s", item)

    session.execute(sa.delete(ChunkReference))
    for i in range(0, len(rows), BATCH_SIZE):
        session.execute(sa.insert(ChunkReference), rows[i : i + BATCH_SIZE])
    session.flush()

    logger.info("  inserted %d references", len(rows))
    return {
        "source_rows": len(sources),
        "written": len(rows),
        "missing_source": len(missing_source),
        "missing_target": len(missing_target),
    }


def verify(session: Session, stats: dict[str, int]) -> bool:
    """Confirm the copy is complete and the nullable-target case survived."""
    ok = True

    total = session.scalar(sa.select(sa.func.count()).select_from(ChunkReference))
    external = session.scalar(
        sa.select(sa.func.count()).select_from(ChunkReference).where(ChunkReference.target_chunk_id.is_(None))
    )
    src_table = session.scalar(sa.select(sa.func.count()).select_from(LegalChunkReference))
    review = session.scalar(
        sa.select(sa.func.count()).select_from(ChunkReference).where(ChunkReference.needs_review.is_(True))
    )
    boundary = session.scalar(
        sa.select(sa.func.count())
        .select_from(ChunkReference)
        .where(ChunkReference.needs_reason == "BOUNDARY")
    )
    unresolved = session.scalar(
        sa.select(sa.func.count())
        .select_from(ChunkReference)
        .where(ChunkReference.needs_reason == "UNRESOLVED")
    )
    low = session.scalar(
        sa.select(sa.func.count()).select_from(ChunkReference).where(ChunkReference.confidence == "LOW")
    )

    src_external = session.scalar(
        sa.select(sa.func.count())
        .select_from(LegalChunkReference)
        .where(LegalChunkReference.target_chunk_id.is_(None))
    )

    logger.info("  rows: %d (source table: %d)", total, src_table)
    logger.info("  external (NULL target): %d (source table: %d)", external, src_external)
    logger.info("  needs_review: %d  BOUNDARY: %d  UNRESOLVED: %d", review, boundary, unresolved)
    logger.info("  confidence LOW: %d", low)

    if stats["missing_source"]:
        logger.error("  FAIL: %d source chunks could not be mapped", stats["missing_source"])
        ok = False
    if total != src_table - stats["missing_source"]:
        logger.error("  FAIL: expected %d rows", src_table - stats["missing_source"])
        ok = False
    if external != src_external:
        logger.error("  FAIL: external count drifted (%d vs %d)", external, src_external)
        ok = False
    if unresolved:
        logger.error("  FAIL: UNRESOLVED should be 0")
        ok = False
    return ok


def main() -> None:
    logger.info("=" * 60)
    logger.info("copy_chunk_references.py — legal_chunk_references -> chunk_references")
    logger.info("=" * 60)
    logger.info("Database: %s:%s/%s", settings.DB_HOST, settings.DB_PORT, settings.DB_NAME)

    db: Session = SessionLocal()
    try:
        logger.info("\n=== Copy ===")
        stats = copy_references(db)
        db.commit()

        logger.info("\n=== Verify ===")
        ok = verify(db, stats)
        if ok:
            logger.info("OK: graph copied")
        else:
            logger.error("FAILED: see the messages above")

        logger.info("\n=== Done ===")
    except Exception:
        db.rollback()
        logger.exception("Copy failed - rolled back")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
