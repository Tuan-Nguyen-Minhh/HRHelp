"""Tour nhanh database final (CHỈ ĐỌC, không ghi gì).

Usage:
    python scripts/show_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import sqlalchemy as sa  # noqa: E402

from src.core.config import settings  # noqa: E402

e = sa.create_engine(settings.SYNC_DATABASE_URI)
W = 100


def q(c, sql, **p):
    return c.execute(sa.text(sql), p)


with e.connect() as c:
    print("=" * W)
    print("1. TABLES + ROW COUNTS (1 database duy nhất: build_phase_p029)")
    print("=" * W)
    for t, n in q(c, "SELECT 'legal_documents', count(*) FROM legal_documents "
                     "UNION ALL SELECT 'legal_chunks', count(*) FROM legal_chunks "
                     "UNION ALL SELECT 'legal_chunk_references', count(*) FROM legal_chunk_references "
                     "UNION ALL SELECT 'legal_chunk_embeddings', count(*) FROM legal_chunk_embeddings "
                     "UNION ALL SELECT 'alembic_version', count(*) FROM alembic_version"):
        print(f"  {t:<28} {n}")
    print("  alembic head:", q(c, "SELECT version_num FROM alembic_version").scalar())

    print("\n" + "=" * W)
    print("2. legal_documents — 3 văn bản (full row)")
    print("=" * W)
    for r in q(c, "SELECT * FROM legal_documents ORDER BY document_id").mappings():
        print(f"  {r['doc_code']:<10} {r['document_id']:<18} {r['status']:<17} "
              f"articles={r['article_count']} chunks={r['chunk_count']}")
        print(f"             title={r['title']}")
        print(f"             amended_by={'NULL' if r['amended_by'] is None else str(r['amended_by'])[:120]}")

    print("\n" + "=" * W)
    print("3. legal_chunks — phân bố cấp chunk × văn bản + 1 row mẫu full cột")
    print("=" * W)
    for doc, lvl, n in q(c, "SELECT document_id, chunk_level, count(*) FROM legal_chunks "
                            "GROUP BY 1,2 ORDER BY 1,2"):
        print(f"  {doc:<18} {lvl:<8} {n}")
    r = q(c, "SELECT * FROM legal_chunks WHERE chunk_id='BLLD:CVIII:M01:A122:C02'").mappings().first()
    print("\n  --- 1 row mẫu: BLLD:CVIII:M01:A122:C02 ---")
    for k in ("chunk_id", "document_id", "parent_chunk_id", "article_number",
              "clause_number", "point_letter", "chunk_level"):
        print(f"  {k:<16}: {r[k]}")
    print(f"  header_context : {str(r['header_context'])[:130]}")
    print(f"  text           : {r['text'][:200]}")
    print(f"  meta keys      : {sorted((r['meta'] or {}).keys())}")

    print("\n" + "=" * W)
    print("4. legal_chunk_references — đồ thị dẫn chiếu (565 cạnh)")
    print("=" * W)
    for rule, n in q(c, "SELECT rule, count(*) FROM legal_chunk_references GROUP BY 1 ORDER BY 2 DESC"):
        print(f"  {rule or '(rule rỗng)':<22} {n}")
    print("\n  --- cạnh đi RA từ ND283 A044:C01 ---")
    for s, td, a, cl, pt, tgt in q(c, "SELECT source_chunk_id, target_doc, article, clause, point, "
                                      "target_chunk_id FROM legal_chunk_references "
                                      "WHERE source_chunk_id='ND283_2026:CIII:M00:A044:C01'"):
        print(f"  -> {td} Điều {a} khoản {cl} điểm {pt} | target_chunk={tgt}")
    print("\n  --- cạnh đi VÀO Điều 169 BLLD (2 nguồn từ NĐ145) ---")
    for s in q(c, "SELECT DISTINCT source_chunk_id FROM legal_chunk_references "
                  "WHERE target_doc='18/VBHN-VPQH' AND article=169 ORDER BY 1").scalars():
        print(f"  <- {s}")

    print("\n" + "=" * W)
    print("5. legal_chunk_embeddings — vector + BM25 (B6/B7)")
    print("=" * W)
    print("  dims != 1024   :", q(c, "SELECT count(*) FROM legal_chunk_embeddings "
                                     "WHERE vector_dims(embedding) <> 1024").scalar())
    print("  model != mistral-embed:", q(c, "SELECT count(*) FROM legal_chunk_embeddings "
                                            "WHERE model <> 'mistral-embed'").scalar())
    print("  search_tsv NULL:", q(c, "SELECT count(*) FROM legal_chunk_embeddings "
                                     "WHERE search_tsv IS NULL").scalar())
    print("  stale sha      :", q(c, "SELECT count(*) FROM legal_chunk_embeddings e "
                                     "JOIN legal_chunks c ON c.chunk_id=e.chunk_id "
                                     "WHERE e.content_sha256 <> encode(digest(c.text,'sha256'),'hex')").scalar()
              if q(c, "SELECT count(*) FROM pg_extension WHERE extname='pgcrypto'").scalar() else "  (bỏ qua: thiếu pgcrypto)")
    print("\n  --- join 3 bảng: chunk + vector + số cạnh dẫn chiếu ---")
    for cid, doc, art, lvl, d, nref in q(c,
            "SELECT c.chunk_id, c.document_id, c.article_number, c.chunk_level, "
            "       vector_dims(e.embedding) AS d, "
            "       (SELECT count(*) FROM legal_chunk_references r "
            "         WHERE r.source_chunk_id=c.chunk_id) AS nref "
            "FROM legal_chunks c JOIN legal_chunk_embeddings e ON e.chunk_id=c.chunk_id "
            "WHERE c.chunk_id IN ('BLLD:CXII:M00:A169:C02','ND283_2026:CIII:M00:A044:C01','ND145_2020:CI:M00:A001') "
            "ORDER BY c.chunk_id"):
        print(f"  {cid:<34} {doc.split('/')[0]:<4} D{art:<4} {lvl:<7} vec={d} refs_out={nref}")

    print("\n" + "=" * W)
    print("6. INDEXES trên 4 bảng legal")
    print("=" * W)
    for t, ix in q(c, "SELECT tablename, indexname FROM pg_indexes "
                       "WHERE tablename LIKE 'legal\\_%' ORDER BY 1,2"):
        print(f"  {t:<26} {ix}")
print()
