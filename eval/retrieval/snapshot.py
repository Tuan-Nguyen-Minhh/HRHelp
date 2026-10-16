"""Chụp kho truy xuất và đồ thị bằng giao dịch chỉ đọc, không tạo vector."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fingerprint(snapshot):
    payload = {key: snapshot[key] for key in ("chunks", "references")}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_corpus():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    from src.core.config import settings

    connection = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        connect_timeout=10,
    )
    connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT c.id::text AS chunk_id, c.document_id::text AS document_id,
                       c.chunk_index, c.content, c.section_title, c.article, c.clause, c.point,
                       c.metadata AS metadata, c.embedding IS NOT NULL AS has_embedding,
                       vector_dims(c.embedding) AS embedding_dimensions,
                       c.embedding::text AS embedding_text,
                       d.ingest_status, (d.deleted_at IS NOT NULL) AS document_deleted,
                       v.id::text AS policy_version_id, v.version, v.status AS version_status,
                       v.effective_from::text, v.effective_to::text,
                       p.code AS policy_code, p.policy_type, p.name AS policy_name, p.is_active,
                       (p.deleted_at IS NOT NULL) AS policy_deleted
                FROM document_chunks c
                JOIN documents d ON d.id=c.document_id
                JOIN policy_versions v ON v.id=d.policy_version_id
                JOIN policies p ON p.id=v.policy_id
                ORDER BY c.id
            """)
            chunks = [dict(row) for row in cursor.fetchall()]
            cursor.execute("""
                SELECT source_chunk_id::text, target_chunk_id::text, target_doc, article, clause, point,
                       rule, confidence, needs_review, needs_reason
                FROM chunk_references
                ORDER BY source_chunk_id, target_chunk_id NULLS FIRST, target_doc, article, clause NULLS FIRST,
                         point NULLS FIRST, rule, confidence, needs_review, needs_reason NULLS FIRST
            """)
            references = [dict(row) for row in cursor.fetchall()]
        for chunk in chunks:
            chunk["content_sha256"] = hashlib.sha256(chunk["content"].encode()).hexdigest()
            vector = chunk.pop("embedding_text")
            chunk["embedding_sha256"] = hashlib.sha256(vector.encode()).hexdigest() if vector is not None else None
        snapshot = {
            "schema_version": 1,
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "scope_vi": "Ảnh chụp cơ sở dữ liệu đang chạy; chưa xác thực nguồn pháp lý hoặc ngày hiệu lực.",
            "chunks": chunks,
            "references": references,
        }
        snapshot["corpus_sha256"] = fingerprint(snapshot)
        return snapshot
    finally:
        connection.rollback()
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "corpus_snapshot.json")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("Đã có ảnh chụp; dùng --output khác hoặc --overwrite")
    snapshot = read_corpus()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "chunks": len(snapshot["chunks"]),
                "references": len(snapshot["references"]),
                "by_policy": dict(Counter(c["policy_code"] for c in snapshot["chunks"])),
                "corpus_sha256": snapshot["corpus_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
