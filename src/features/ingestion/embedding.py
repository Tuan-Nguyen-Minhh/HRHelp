"""Phase 2: embed an ingested document's chunks, off the request thread.

The slow part (Mistral, 1 RPS) runs here; the request already wrote the chunks
with a NULL vector, so a crash mid-embedding only leaves the document in
``CHUNKED`` and the retry endpoint resumes from the database.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from src.common.audit import write_audit
from src.db.session import SessionLocal
from src.models.document_chunks import DocumentChunk
from src.models.documents import Document
from src.services.embeddings_client import PURPOSE_CORPUS, EmbeddingClient

from .writer import embedding_input

logger = logging.getLogger(__name__)

BATCH_SIZE = 32

# Strong references to in-flight tasks: without this the event loop may garbage
# collect a task before it finishes.
_tasks: set[asyncio.Task] = set()


def schedule(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _pending(session, document_id: UUID) -> list[DocumentChunk]:
    rows = await session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_(None))
        .order_by(DocumentChunk.chunk_index)
    )
    return list(rows.all())


async def embed_document(document_id: UUID, actor_id: UUID | None = None) -> None:
    async with SessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            return
        try:
            pending = await _pending(session, document_id)
            if not pending:
                document.ingest_status = "EMBEDDED"
                await session.commit()
                return

            client = EmbeddingClient()
            for start in range(0, len(pending), BATCH_SIZE):
                batch = pending[start:start + BATCH_SIZE]
                inputs = [embedding_input(chunk) for chunk in batch]
                vectors = await asyncio.to_thread(
                    client.embed,
                    inputs,
                    purpose=PURPOSE_CORPUS,
                    run_id=f"ingest-{document_id}",
                    chunk_ids=[str(chunk.id) for chunk in batch],
                )
                for chunk, vector in zip(batch, vectors, strict=True):
                    chunk.embedding = vector
                await session.flush()
                await session.commit()

            document.ingest_status = "EMBEDDED"
            await write_audit(
                session,
                case_id=None,
                actor_id=actor_id,
                actor_role=None,
                action="DOCUMENT_INGESTED",
                entity_type="documents",
                entity_id=document.id,
                after={"ingest_status": "EMBEDDED", "chunk_count": len(pending)},
            )
            await session.commit()
        except Exception as exc:
            logger.exception("document embed failed document_id=%s", document_id)
            document.ingest_status = "FAILED"
            await write_audit(
                session,
                case_id=None,
                actor_id=actor_id,
                actor_role=None,
                action="DOCUMENT_INGEST_FAILED",
                entity_type="documents",
                entity_id=document.id,
                after={"ingest_status": "FAILED", "error": f"{type(exc).__name__}: {exc}"[:500]},
            )
            await session.commit()
