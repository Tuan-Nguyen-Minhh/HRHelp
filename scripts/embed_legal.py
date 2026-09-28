"""B6: embed the 1289 legal chunks into ``legal_chunk_embeddings``.

Plan: ``data_pipeline_steps/step6_7_plan.md`` section 2 (B6).

What it does, in order:

1. **Preflight before spending anything.** Refuses to run unless
   ``EMBEDDING_MODEL``/``EMBEDDING_DIMENSIONS`` still match the frozen contract,
   ``MISTRAL_API_KEY`` is present, alembic is at head ``0003_legal_embeddings``
   and ``legal_chunks`` holds exactly 1289 rows. A wrong model would write
   vectors that V4 then reports as garbage, and a wrong row count would mean
   silently embedding the wrong corpus.

2. **Reads the corpus from the database**, not from the JSON files, ordered by
   ``chunk_id`` ascending. ``content_sha256`` is defined as the sha256 of
   ``legal_chunks.text``, so the text that gets embedded and the text that gets
   hashed have to be the same bytes — the database column is the source of truth.

3. **Resume.** A chunk is skipped only when it already has an embedding row
   *and* its stored ``content_sha256`` equals the sha256 of the current
   ``legal_chunks.text``. A changed text therefore re-embeds exactly one row,
   and a crash costs at most the current batch.

4. **Batches of 32 texts per request.** 1289 chunks / 32 = 41 requests, ~41 s
   at 1 RPS. Unbatched it would be ~22 minutes for the same tokens — batching
   is a quota decision, not a nicety.

5. **1 RPS and a per-request audit log** are enforced by
   ``src.services.embeddings_client``, shared with every other caller of the
   Mistral embeddings endpoint so the team budget holds across scripts.

The 3 chunks whose body exceeds the 1000-token step3 threshold are embedded
normally (mistral-embed takes 8k) and their ``POINT_BODY_OVER_LIMIT`` flag from
``legal_chunks.meta.anomaly_flags`` is reported in the log and in the
checkpoint, so the audit trail keeps it instead of losing it.

Usage:
    python scripts/embed_legal.py            # embed what is missing
    python scripts/embed_legal.py --dry-run  # report, spend nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402
from src.models.legal import (  # noqa: E402
    EMBEDDING_DIM,
    EMBEDDING_MODEL_NAME,
    LegalChunk,
    LegalChunkEmbedding,
)
from src.services.embeddings_client import (  # noqa: E402
    PURPOSE_CORPUS,
    EmbeddingClient,
    new_run_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("embed_legal")

# ---------------------------------------------------------------------------
# Frozen inputs / expectations (plan 1 and 2.2). Hard numbers, never recomputed
# from whatever the database happens to contain.
# ---------------------------------------------------------------------------

CHUNK_DIR = PROJECT_ROOT / "data" / "chunk"
CHECKPOINT_PATH = CHUNK_DIR / "embed_progress.json"

EXPECTED_TOTAL_CHUNKS = 1289
EXPECTED_ALEMBIC_HEAD = "0003_legal_embeddings"

#: Texts per Mistral request. 32 is the plan's value: 41 requests instead of
#: 1289, which is the difference between ~41 s and ~22 min of wall clock.
BATCH_SIZE = 32

#: The 3 step3 chunks over the 1000-token threshold. Embedded anyway (the model
#: takes 8k); the flag is carried through to the audit log.
OVER_LIMIT_FLAG = "POINT_BODY_OVER_LIMIT"

_engine = sa.create_engine(settings.SYNC_DATABASE_URI)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_text(header_context: str | None, text: str) -> str:
    """The exact string sent to the model: ``header_context + "\\n" + text``.

    Frozen by plan 2.2. The header carries the Văn bản / Chương / Mục / Điều
    breadcrumb, which is the context a legal question needs; embedding without
    it would make Điều 107 of NĐ145 indistinguishable from Điều 107 of the Bộ
    luật Lao động. A NULL header contributes nothing rather than a leading
    newline.
    """
    return f"{header_context}\n{text}" if header_context else text


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

def preflight(db: Session) -> None:
    problems: list[str] = []

    if settings.EMBEDDING_MODEL != EMBEDDING_MODEL_NAME:
        problems.append(
            f"EMBEDDING_MODEL={settings.EMBEDDING_MODEL!r} but the frozen "
            f"contract is {EMBEDDING_MODEL_NAME!r}"
        )
    if settings.EMBEDDING_DIMENSIONS != EMBEDDING_DIM:
        problems.append(
            f"EMBEDDING_DIMENSIONS={settings.EMBEDDING_DIMENSIONS} but the "
            f"table is Vector({EMBEDDING_DIM})"
        )
    if not settings.MISTRAL_API_KEY:
        problems.append("MISTRAL_API_KEY is empty (plan section 1 prerequisite)")

    current = db.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    if current != EXPECTED_ALEMBIC_HEAD:
        problems.append(
            f"alembic current={current!r}, expected {EXPECTED_ALEMBIC_HEAD!r}; "
            "run `alembic upgrade head` first"
        )

    n_chunks = db.scalar(sa.select(sa.func.count()).select_from(LegalChunk))
    if n_chunks != EXPECTED_TOTAL_CHUNKS:
        problems.append(
            f"legal_chunks holds {n_chunks} rows, expected {EXPECTED_TOTAL_CHUNKS}; "
            "B4 is not in its verified state"
        )

    if problems:
        raise SystemExit(
            "preflight failed — refusing to spend quota:\n  - "
            + "\n  - ".join(problems)
        )
    logger.info(
        f"preflight ok: model={settings.EMBEDDING_MODEL} "
        f"dim={settings.EMBEDDING_DIMENSIONS} chunks={n_chunks} alembic={current}"
    )


# ---------------------------------------------------------------------------
# Corpus + resume state
# ---------------------------------------------------------------------------

def load_chunks(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        sa.select(
            LegalChunk.chunk_id,
            LegalChunk.header_context,
            LegalChunk.text,
            LegalChunk.meta,
        ).order_by(LegalChunk.chunk_id)
    ).mappings()
    return [dict(r) for r in rows]


def load_stored_hashes(db: Session) -> dict[str, str]:
    rows = db.execute(
        sa.select(LegalChunkEmbedding.chunk_id, LegalChunkEmbedding.content_sha256)
    )
    # CHAR(64) may come back space-padded on some drivers; normalise so a
    # comparison here can never disagree with the SQL `=` in V2.
    return {cid: (sha or "").strip() for cid, sha in rows}


def over_limit_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    out = []
    for c in chunks:
        flags = (c.get("meta") or {}).get("anomaly_flags") or []
        if OVER_LIMIT_FLAG in flags:
            out.append(c["chunk_id"])
    return out


# ---------------------------------------------------------------------------
# Checkpoint (transient state, gitignored — the DB is the real resume state)
# ---------------------------------------------------------------------------

def write_checkpoint(payload: dict[str, Any]) -> None:
    payload["updated_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="B6: embed legal_chunks")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be embedded without calling the API",
    )
    args = parser.parse_args()

    logger.info("Starting embed_legal.py")
    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    db: Session = SessionLocal()
    try:
        preflight(db)
        chunks = load_chunks(db)
        stored = load_stored_hashes(db)
        over_limit = over_limit_chunks(chunks)

        pending: list[dict[str, Any]] = []
        skipped = 0
        for c in chunks:
            c["content_sha256"] = sha256_text(c["text"])
            if stored.get(c["chunk_id"]) == c["content_sha256"]:
                skipped += 1
            else:
                pending.append(c)

        logger.info(f"chunks: {len(chunks)} total, {skipped} up to date, {len(pending)} to embed")
        logger.info(
            f"over {OVER_LIMIT_FLAG} (embedded anyway, model limit is 8k): {len(over_limit)} "
            f"-> {over_limit}"
        )
        batches = [pending[i : i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
        logger.info(
            f"plan: {len(batches)} request(s) of up to {BATCH_SIZE} texts "
            f"(~{len(batches) * 1.0:.0f}s at 1 RPS)"
        )

        run_id = new_run_id("corpus")
        checkpoint: dict[str, Any] = {
            "run_id": run_id,
            "model": settings.EMBEDDING_MODEL,
            "dimensions": settings.EMBEDDING_DIMENSIONS,
            "batch_size": BATCH_SIZE,
            "embed_text": "header_context + '\\n' + text",
            "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "total_chunks": len(chunks),
            "skipped": skipped,
            "embedded": 0,
            "requests": 0,
            "dry_run": args.dry_run,
            "over_limit_flag": OVER_LIMIT_FLAG,
            "over_limit_chunk_ids": over_limit,
        }
        write_checkpoint(checkpoint)

        if args.dry_run:
            logger.info("DRY RUN — no API call, no write")
            return 0

        if not pending:
            logger.info("nothing to do: every chunk already has a fresh embedding")
            return 0

        client = EmbeddingClient()
        tokens = 0
        for n, batch in enumerate(batches, start=1):
            texts = [embed_text(c["header_context"], c["text"]) for c in batch]
            ids = [c["chunk_id"] for c in batch]
            vectors = client.embed(
                texts, purpose=PURPOSE_CORPUS, run_id=run_id, chunk_ids=ids
            )
            rows = [
                {
                    "chunk_id": c["chunk_id"],
                    "content_sha256": c["content_sha256"],
                    "model": settings.EMBEDDING_MODEL,
                    "dimensions": settings.EMBEDDING_DIMENSIONS,
                    "header_context": c["header_context"],
                    "text": c["text"],
                    "embedding": v,
                }
                for c, v in zip(batch, vectors, strict=True)
            ]
            stmt = pg_insert(LegalChunkEmbedding).values(rows)
            # updated_at must be set explicitly: SQLAlchemy's onupdate only
            # fires for ORM UPDATE statements, not for on_conflict_do_update.
            stmt = stmt.on_conflict_do_update(
                index_elements=["chunk_id"],
                set_={
                    "content_sha256": stmt.excluded.content_sha256,
                    "model": stmt.excluded.model,
                    "dimensions": stmt.excluded.dimensions,
                    "header_context": stmt.excluded.header_context,
                    "text": stmt.excluded.text,
                    "embedding": stmt.excluded.embedding,
                    "updated_at": sa.func.now(),
                },
            )
            # One transaction per batch: a crash costs at most one batch, and
            # the next run resumes from content_sha256 in the database.
            db.execute(stmt)
            db.commit()

            checkpoint.update(
                embedded=checkpoint["embedded"] + len(batch),
                requests=checkpoint["requests"] + 1,
                last_chunk_id=ids[-1],
            )
            write_checkpoint(checkpoint)
            logger.info(
                f"  batch {n}/{len(batches)}: {len(batch)} chunk(s) "
                f"({checkpoint['embedded']}/{len(pending)}), last={ids[-1]}"
            )

        # The API reported prompt_tokens per request; re-read the log for this
        # run so the printed total is the server's number, not our estimate.
        from src.services.embeddings_client import read_call_log  # local: audit only

        tokens = sum(
            rec.get("prompt_tokens") or 0
            for rec in read_call_log()
            if rec.get("run_id") == run_id and rec.get("status") == "ok"
        )
        total_rows = db.scalar(sa.select(sa.func.count()).select_from(LegalChunkEmbedding))
        logger.info("")
        logger.info("=" * 72)
        logger.info(f"run_id           : {run_id}")
        logger.info(f"skipped (fresh)  : {skipped}")
        logger.info(f"embedded         : {checkpoint['embedded']}")
        logger.info(f"API requests     : {checkpoint['requests']}")
        logger.info(f"prompt tokens    : {tokens}")
        logger.info(f"rows in table    : {total_rows}")
        logger.info("=" * 72)
        return 0
    except Exception:
        db.rollback()
        logger.exception("Embedding failed — rolled back this batch")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
