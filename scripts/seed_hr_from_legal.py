"""Seed HR tables from legal_* tables: one-time ETL migration.

Reads from legal_documents → legal_chunks → legal_chunk_embeddings and writes
into policies → policy_versions → documents → document_chunks using new UUIDs.

The original semantic chunk_id (e.g. 'BLLD:CVIII:M01:A125') is preserved in
chunk_metadata['legal_chunk_id'] for traceability. The original legal_document_id
is preserved in chunk_metadata['legal_document_id'].

After this script runs and is verified, the legal_* tables can be dropped.

Idempotent: uses ON CONFLICT DO UPDATE on policies.code, so re-running is safe.
For document_chunks, the script deletes existing rows for the 3 legal documents
before re-inserting (same approach as seed_legal.py for legal_chunk_references).

Usage:
    python -m scripts.seed_hr_from_legal
    # or from project root:
    python scripts/seed_hr_from_legal.py
"""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402
from src.models.document_chunks import DocumentChunk  # noqa: E402
from src.models.documents import Document  # noqa: E402
from src.models.legal import (  # noqa: E402
    LegalChunk,
    LegalChunkEmbedding,
    LegalDocument,
)
from src.models.policies import Policy  # noqa: E402
from src.models.policy_versions import PolicyVersion  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_hr_from_legal")

_sync_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(bind=_sync_engine, autoflush=False, expire_on_commit=False)

# ---------------------------------------------------------------------------
# Document mapping: legal_documents → policies + policy_versions + documents
# ---------------------------------------------------------------------------

# Map legal document_type to HR policy_type
_TYPE_MAP = {
    "BO_LUAT": "LAW",
    "NGHI_DINH": "DECREE",
}

LEGAL_DOCS: list[dict[str, Any]] = [
    {
        "legal_document_id": "18/VBHN-VPQH",
        "code": "BLLD_2019",
        "name": "Bộ luật Lao động 2019 (Văn bản hợp nhất)",
        "policy_type": "LAW",
        "effective_from": date(2021, 1, 1),
        "effective_to": None,  # Still in force
    },
    {
        "legal_document_id": "145/2020/NĐ-CP",
        "code": "ND145_2020",
        "name": "Nghị định 145/2020/NĐ-CP hướng dẫn Bộ luật Lao động",
        "policy_type": "DECREE",
        "effective_from": date(2021, 2, 1),
        "effective_to": date(2026, 9, 9),  # Superseded by NĐ283
    },
    {
        "legal_document_id": "283/2026/NĐ-CP",
        "code": "ND283_2026",
        "name": "Nghị định 283/2026/NĐ-CP thay thế NĐ145",
        "policy_type": "DECREE",
        "effective_from": date(2026, 9, 10),
        "effective_to": None,  # Current
    },
    {
        "legal_document_id": "NQLD-HRCORP-2026",
        "code": "NQCT",
        "name": "Nội quy lao động HRCorp",
        "policy_type": "INTERNAL_RULE",
        "effective_from": date(2026, 1, 1),
        "effective_to": None,
    },
]

BATCH_SIZE = 200


# ---------------------------------------------------------------------------
# Step 1: Seed policies
# ---------------------------------------------------------------------------

def seed_policies(db: Session) -> dict[str, Any]:
    """Create/update policies, return {legal_document_id: policy_id}."""
    policy_ids: dict[str, Any] = {}

    for doc in LEGAL_DOCS:
        # Upsert policy
        stmt = pg_insert(Policy).values(
            code=doc["code"],
            name=doc["name"],
            policy_type=doc["policy_type"],
            is_active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["code"],
            set_={
                "name": stmt.excluded.name,
                "policy_type": stmt.excluded.policy_type,
                "is_active": stmt.excluded.is_active,
            },
        ).returning(Policy.id)
        result = db.execute(stmt)
        policy_id = result.scalar_one()
        policy_ids[doc["legal_document_id"]] = policy_id
        logger.info(f"  policy '{doc['code']}' → {policy_id}")

    db.flush()
    return policy_ids


# ---------------------------------------------------------------------------
# Step 2: Seed policy_versions (with ExcludeConstraint protection)
# ---------------------------------------------------------------------------

def seed_policy_versions(
    db: Session, policy_ids: dict[str, Any]
) -> dict[str, Any]:
    """Create policy_versions, return {legal_document_id: policy_version_id}."""
    pv_ids: dict[str, Any] = {}

    for doc in LEGAL_DOCS:
        policy_id = policy_ids[doc["legal_document_id"]]

        # Check if version already exists
        existing = db.execute(
            sa.select(PolicyVersion.id).where(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.version == "1.0",
            )
        ).scalar()

        if existing:
            pv_ids[doc["legal_document_id"]] = existing
            logger.info(f"  policy_version for '{doc['code']}' already exists → {existing}")
            continue

        # Insert new version — ExcludeConstraint protects against date overlap
        stmt = sa.insert(PolicyVersion).values(
            policy_id=policy_id,
            version="1.0",
            effective_from=doc["effective_from"],
            effective_to=doc["effective_to"],
            status="ACTIVE",
        ).returning(PolicyVersion.id)
        result = db.execute(stmt)
        pv_id = result.scalar_one()
        pv_ids[doc["legal_document_id"]] = pv_id
        logger.info(
            f"  policy_version '{doc['code']}' v1.0 "
            f"[{doc['effective_from']} → {doc['effective_to'] or '∞'}] → {pv_id}"
        )

    db.flush()
    return pv_ids


# ---------------------------------------------------------------------------
# Step 3: Seed documents
# ---------------------------------------------------------------------------

def seed_documents(
    db: Session, pv_ids: dict[str, Any]
) -> dict[str, Any]:
    """Create documents, return {legal_document_id: document_uuid}."""
    doc_ids: dict[str, Any] = {}

    for doc in LEGAL_DOCS:
        pv_id = pv_ids[doc["legal_document_id"]]

        # Read title from legal_documents
        legal_doc = db.execute(
            sa.select(LegalDocument).where(
                LegalDocument.document_id == doc["legal_document_id"]
            )
        ).scalar_one()

        # Check if already exists (by matching policy_version_id + file_name)
        existing = db.execute(
            sa.select(Document.id).where(
                Document.policy_version_id == pv_id,
                Document.file_name == legal_doc.title,
            )
        ).scalar()

        if existing:
            doc_ids[doc["legal_document_id"]] = existing
            logger.info(f"  document for '{doc['code']}' already exists → {existing}")
            continue

        stmt = sa.insert(Document).values(
            policy_version_id=pv_id,
            file_name=legal_doc.title,
            file_type="LEGAL_TEXT",
            source=f"legal_documents:{doc['legal_document_id']}",
            ingest_status="EMBEDDED",
        ).returning(Document.id)
        result = db.execute(stmt)
        doc_uuid = result.scalar_one()
        doc_ids[doc["legal_document_id"]] = doc_uuid
        logger.info(f"  document '{legal_doc.title}' → {doc_uuid}")

    db.flush()
    return doc_ids


# ---------------------------------------------------------------------------
# Step 4: Seed document_chunks (the big one)
# ---------------------------------------------------------------------------

def seed_chunks(
    db: Session, doc_ids: dict[str, Any]
) -> int:
    """Copy legal_chunks + embeddings → document_chunks. Returns total count."""
    total = 0

    for doc_info in LEGAL_DOCS:
        legal_doc_id = doc_info["legal_document_id"]
        hr_doc_uuid = doc_ids[legal_doc_id]

        # Delete existing chunks for this document (idempotent re-run)
        deleted = db.execute(
            sa.delete(DocumentChunk).where(
                DocumentChunk.document_id == hr_doc_uuid
            )
        ).rowcount
        if deleted:
            logger.info(f"  cleaned {deleted} existing chunks for {doc_info['code']}")

        # Fetch legal_chunks + embeddings in article/clause order
        chunks_with_embeddings = db.execute(
            sa.select(
                LegalChunk.chunk_id,
                LegalChunk.header_context,
                LegalChunk.text,
                LegalChunk.article_number,
                LegalChunk.clause_number,
                LegalChunk.point_letter,
                LegalChunk.chunk_level,
                LegalChunk.meta,
                LegalChunkEmbedding.embedding,
                LegalChunkEmbedding.content_sha256,
            )
            .outerjoin(
                LegalChunkEmbedding,
                LegalChunkEmbedding.chunk_id == LegalChunk.chunk_id,
            )
            .where(LegalChunk.document_id == legal_doc_id)
            .order_by(
                LegalChunk.article_number,
                LegalChunk.clause_number.nulls_first(),
                LegalChunk.point_letter.nulls_first(),
            )
        ).all()

        # Build rows with sequential chunk_index (UNIQUE constraint)
        rows: list[dict[str, Any]] = []
        for idx, row in enumerate(chunks_with_embeddings):
            # Enrich metadata with traceability info
            meta = dict(row.meta) if row.meta else {}
            meta["legal_chunk_id"] = row.chunk_id
            meta["legal_document_id"] = legal_doc_id
            if row.content_sha256:
                meta["content_sha256"] = row.content_sha256

            rows.append({
                "document_id": hr_doc_uuid,
                "chunk_index": idx,
                "content": row.text,
                "article": str(row.article_number) if row.article_number is not None else None,
                "clause": str(row.clause_number) if row.clause_number is not None else None,
                "point": row.point_letter,
                "section": row.chunk_level,  # 'ARTICLE', 'CLAUSE', 'POINT'
                "section_title": row.header_context,  # breadcrumb
                "chunk_metadata": meta,
                "embedding": row.embedding,
            })

        # Batch insert
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            db.execute(sa.insert(DocumentChunk), batch)

        total += len(rows)
        logger.info(
            f"  {doc_info['code']}: {len(rows)} chunks inserted "
            f"({sum(1 for r in rows if r['embedding'] is not None)} with embeddings)"
        )

    db.flush()
    return total


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify(db: Session) -> bool:
    """Quick sanity checks after ETL."""
    ok = True

    # 1. Check policies exist
    n_policies = db.scalar(
        sa.select(sa.func.count()).select_from(Policy).where(
            Policy.code.in_([d["code"] for d in LEGAL_DOCS])
        )
    )
    logger.info(f"  verify: {n_policies}/4 policies")
    if n_policies != 4:
        ok = False

    # 2. Check total chunks in document_chunks
    n_chunks = db.scalar(
        sa.select(sa.func.count()).select_from(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(PolicyVersion, PolicyVersion.id == Document.policy_version_id)
        .join(Policy, Policy.id == PolicyVersion.policy_id)
        .where(
            Policy.code.in_([d["code"] for d in LEGAL_DOCS]),
            Policy.is_active.is_(True),
            Document.ingest_status.in_(("CHUNKED", "EMBEDDED")),
        )
    )
    logger.info(f"  verify: {n_chunks} chunks accessible via cite._candidate_stmt path")

    # Compare with legal_chunks count
    n_legal = db.scalar(
        sa.select(sa.func.count()).select_from(LegalChunk)
    )
    logger.info(f"  verify: {n_legal} chunks in legal_chunks (source)")
    if n_chunks != n_legal:
        logger.warning(f"  ⚠ chunk count mismatch: HR={n_chunks} vs legal={n_legal}")
        ok = False

    # 3. Check embeddings copied
    n_with_embedding = db.scalar(
        sa.select(sa.func.count()).select_from(DocumentChunk)
        .where(DocumentChunk.embedding.is_not(None))
    )
    n_legal_embeddings = db.scalar(
        sa.select(sa.func.count()).select_from(LegalChunkEmbedding)
    )
    logger.info(
        f"  verify: {n_with_embedding} chunks with embedding "
        f"(legal had {n_legal_embeddings})"
    )
    if n_with_embedding != n_legal_embeddings:
        logger.warning("  ⚠ embedding count mismatch!")
        ok = False

    # 4. Check cite path returns results for a known incident_date
    test_date = date(2024, 6, 1)  # Should match BLLD and ND145
    n_in_force = db.scalar(
        sa.text("""
            SELECT COUNT(*) FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            JOIN policy_versions pv ON pv.id = d.policy_version_id
            JOIN policies p ON p.id = pv.policy_id
            WHERE pv.status = 'ACTIVE'
              AND p.is_active = TRUE
              AND d.ingest_status IN ('CHUNKED', 'EMBEDDED')
              AND pv.effective_from <= :dt
              AND (pv.effective_to IS NULL OR pv.effective_to >= :dt)
        """),
        {"dt": test_date},
    )
    logger.info(
        f"  verify: cite with incident_date={test_date} → {n_in_force} in-force chunks"
    )
    if n_in_force == 0:
        logger.warning("  ⚠ cite would return 0 results!")
        ok = False

    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=" * 60)
    logger.info("seed_hr_from_legal.py — ETL: legal_* → HR tables")
    logger.info("=" * 60)
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    db: Session = SessionLocal()
    try:
        # Step 1: Policies
        logger.info("\n=== Step 1: Seed policies ===")
        policy_ids = seed_policies(db)
        db.commit()

        # Step 2: Policy versions
        logger.info("\n=== Step 2: Seed policy_versions ===")
        pv_ids = seed_policy_versions(db, policy_ids)
        db.commit()

        # Step 3: Documents
        logger.info("\n=== Step 3: Seed documents ===")
        doc_ids = seed_documents(db, pv_ids)
        db.commit()

        # Step 4: Chunks + embeddings (one transaction)
        logger.info("\n=== Step 4: Seed document_chunks (with embeddings) ===")
        total = seed_chunks(db, doc_ids)
        db.commit()
        logger.info(f"  total: {total} document_chunks inserted")

        # Verify
        logger.info("\n=== Verify ===")
        ok = verify(db)
        if ok:
            logger.info("✅ All checks passed!")
        else:
            logger.warning("⚠ Some checks failed — review output above")

        logger.info("\n=== ETL complete ===")

    except Exception:
        db.rollback()
        logger.exception("ETL failed — rolled back")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
