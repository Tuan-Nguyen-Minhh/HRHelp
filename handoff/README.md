# Handoff — snapshot database (bản full + lịch sử)

_Ngày: 2026-09-27 (B4/B5), bổ sung 2026-09-28 (B6/B7), đổi tên dump `b6b7_*` → `full_*`
2026-09-29, bổ sung tài liệu nội bộ NQCT + fix qualifier trần 2026-10-01 (xem
`data/chunk/CHANGELOG.md` mục mới nhất). Nguồn: PostgreSQL 16.15 + pgvector 0.8.6, container `p-029-db-1`._

## 0. Dùng bản nào — đọc trước

- **Máy mới / deploy: chỉ dùng `full_build_phase_p029.dump`.** Đó là snapshot
  **full** của cả database — đủ 4 bảng legal
  (documents 4 / chunks 1377 / references 599 / **embeddings 1377**).
- `b4b5_*` là **lịch sử**, giữ lại để biết B4/B5 bàn giao cái gì. Nó **thiếu
  bảng vector** — import bản này rồi chạy `verify_db.py` thì xanh nhưng
  `verify_embeddings.py` đỏ ngay. Đừng dùng để deploy.

## 1. Có gì trong thư mục này

| File | Kích thước | Dùng để |
|---|---|---|
| `full_build_phase_p029.dump` | ~11,0 MB | **DÙNG BẢN NÀY để import** — snapshot full ở head `0009`, định dạng custom của `pg_dump`, nén `-Z 9` |
| `full_build_phase_p029.dump.sha256` | — | Kiểm tra file còn nguyên (toàn bộ `handoff/` đã commit vào git) |
| `full_build_phase_p029.schema.sql` | 50 KB | **Chỉ phần schema, không có data** — để đọc/diff/review DDL (nhất là `0003`); KHÔNG dùng để import |
| `b4b5_build_phase_p029.dump` | 290 KB | Lịch sử B4/B5 (thiếu bảng vector) — không dùng để deploy |
| `b4b5_build_phase_p029.dump.sha256` | — | Kiểm tra file lịch sử còn nguyên |
| `b4b5_build_phase_p029.sql` | 2,4 MB | SQL thuần B4/B5, để đọc/diff/review |
| `source_manifest.json` | — | sha256 của 6 file JSON nguồn mà B4/B5 đọc vào |

Cả thư mục `handoff/` đã nằm trong git, clone về là có đủ — không cần
chuyển file qua Zalo/Drive.

> Team member đổ data mới / thêm văn bản mới: đọc
> [`RUNBOOK_DO_DATA_MOI.md`](./RUNBOOK_DO_DATA_MOI.md) — checklist từng bước +
> số kỳ vọng + sự cố thường gặp.

## 2. Import vào máy mới (bản full) — 1 lệnh

```powershell
docker compose up -d db   # bật Postgres trước, chờ healthy (docker ps)
powershell -ExecutionPolicy Bypass -File scripts/restore_handoff.ps1
```

Script tự làm hết: check container → check sha256 của dump → copy vào
container → `pg_restore` (`--clean --if-exists`, chạy lại thoải mái).
Xong chạy `python scripts/verify_db.py` (kỳ vọng 77 PASS, 0 FAIL).

Làm tay (khi script không chạy được, VD container tên khác — kiểm tra bằng
`docker ps` rồi thay tên):

```powershell
certutil -hashfile handoff\full_build_phase_p029.dump SHA256
# phải khớp handoff\full_build_phase_p029.dump.sha256:
# 31ACFE408E0CFB97AB9334F7CA3747B3F22399880C93C122BE19EB6BCF3433AF
docker cp handoff\full_build_phase_p029.dump p-029-db-1:/tmp/full.dump
docker exec p-029-db-1 pg_restore -U postgres -d build_phase_p029 --no-owner --no-privileges --clean --if-exists /tmp/full.dump
```
```

**Không cần chạy Alembic** — dump đã chứa cả bảng `alembic_version` với giá trị
`0004_document_chunks_tsv`, và cả extension `vector` sẽ được tạo lại nếu máy mới thiếu
(yêu cầu image Postgres có pgvector, giống `p029-postgres`).

## 3. Nội dung (bản full)

| Bảng | Số dòng | Ý nghĩa |
|---|---|---|
| `policies` | 4 | 3 văn bản luật (BLLĐ 2019, NĐ 145/2020, NĐ 283/2026) + Nội quy HRCorp (`INTERNAL_RULE`) |
| `policy_versions` | 4 | Thời gian hiệu lực từng văn bản (bảo vệ bằng ExcludeConstraint) |
| `documents` | 4 | Bản ghi tài liệu nguồn (`ingest_status='EMBEDDED'`) |
| `document_chunks` | 1377 | 1377 chunks đầy đủ text, vector 1024-dim, và search_tsv (GIN) |
| `legal_documents` | 4 | 3 văn bản luật + 1 nội quy (`NOI_QUY`/`VAN_BAN_NOI_BO`) + footnote sửa đổi |
| `legal_chunks` | 1377 | Nội dung đã chia nhỏ (Điều / khoản / điểm), 88 chunk NQCT đánh số tuần tự 1–82 |
| `legal_chunk_references` | 599 | Đồ thị dẫn chiếu (NQCT: 21 EXPLICIT + 4 EXPLICIT_SELF + 6 LIST_EXPANSION + 2 DEFAULT_SELF, 0 BOUNDARY; BOUNDARY toàn corpus = 3) |
| `legal_chunk_embeddings` | 1377 | Vector `mistral-embed` 1024-dim + tsvector BM25 (B6/B7) |
| `alembic_version` | 1 | Phiên bản migration đã áp dụng (`0009_assessment_form`) |

> **Số trên lấy từ `scripts/corpus_expectations.py`** (tự dẫn từ
> `data/chunk/chunks_*.json`), không gõ tay. Chạy
> `python scripts/corpus_expectations.py` để in lại bất cứ lúc nào.
> `full_build_phase_p029.dump` đã refresh ở head `0009_assessment_form` sau lần
> mở rộng NQCT (2026-10-03) và đã được `pg_restore` thử vào DB tạm để đối chiếu
> (4 / 1377 / 599 / 1377 / 1377, 0 embedding NULL) trước khi thay thế.

Chi tiết B4/B5: `data/chunk/CHANGELOG_B4B5.md`. Chi tiết B6/B7:
`data/chunk/CHANGELOG_B6B7.md`.

## 4. Sau khi import phải chạy lại verify

Không tin lời tôi, tự kiểm. Cần `data/chunk/*.json` (8 file: 4 chunks + 4 tree) và
`data/chunk/source_manifest.json` trong repo:

```bash
python -m alembic upgrade head      # no-op, dump đã ở head
python scripts/verify_db.py         # 77 check B4/B5
python scripts/verify_embeddings.py # 76 check + 2 FAIL đã biết (V4/V5 đường
                                    # vector-only — xem CHANGELOG_B6B7.md mục 5)
```

Kết quả mong đợi: `Total: 77 PASS, 0 FAIL` cho `verify_db.py`;
`Total: 76 PASS, 2 FAIL` cho `verify_embeddings.py`.

## 4-bis. Đã kiểm chứng dump full 2026-10-01 thế nào

Dump mới (`full_build_phase_p029.dump`, có NQCT) đã được `pg_restore` vào
database tạm `p029_restore_verify` trên chính container này rồi so với database
nguồn trước khi xóa DB tạm:

| Hạng mục | Kết quả |
|---|---|
| Số dòng 5 bảng (`legal_documents`/`legal_chunks`/`legal_chunk_references`/`legal_chunk_embeddings`/`document_chunks`) | 4 / 1307 / 568 / 1307 / 1307 — khớp |
| md5 `chunk_id` + mẫu `text` toàn bộ `legal_chunks` | `7e96921afb1c0eb942bd37520f8d5c43` — khớp |
| md5 toàn bộ `legal_chunk_references` | `8d871e6a618131b49788d0210b45de59` — khớp |

## 5. Đã kiểm chứng thế nào (bản `b4b5` — lịch sử, không phải bản deploy)

Dump **này** (`b4b5_*`) không chỉ được tạo rồi đem đi. Nó đã được restore vào
một database tạm `p029_restore_test` trên chính container này, rồi so sánh với
database nguồn:

| Hạng mục | Kết quả |
|---|---|
| Số dòng 3 bảng | khớp |
| `alembic_version` | `0001_legal_schema` |
| Số Điều / chunk từng văn bản | khớp |
| Số parent treo | 1030 |
| `needs_reason` | `BOUNDARY=3`, không cờ=562 |
| `target_chunk_id` NULL | 60 |
| Phân bố 7 loại `rule` | khớp |
| Phân bố chunk theo cấp × văn bản | khớp |
| **md5 toàn bộ 1289 chunk** (`chunk_id`+`text`) | `e3e722948185c78bf152e9298109860e` — khớp |
| **md5 toàn bộ 565 refs** | `50ae6e91147cf0b74ba1db49b7be2ae0` — khớp |
| `amended_by` JSONB của BLLD | khớp |
| Số CHECK constraint (4) và index (12) | khớp |

Database tạm đã được xoá sau khi so sánh; container chỉ còn `postgres` và
`build_phase_p029`.

## 5-bis. Thống nhất embedding: mistral-embed 1024-dim (2026-09-28)

Toàn bộ database dùng một model embedding duy nhất theo DECISION 2026-09-26.
Hai cột `Vector(1536)` cũ (`document_chunks.embedding`,
`disciplinary_decisions.embedding`) là di sản của template OpenAI —
không code nào từng ghi vào đó, DB dev trống cả hai cột. Migration
`0002_unify_mistral_embed` đổi cả hai về `Vector(1024)` và dựng lại index HNSW.
Migration từ chối chạy nếu cột còn vector non-null thay vì cắt ngắn thành rác.

Bảng legal (B6) có bảng embedding riêng (`legal_chunk_embeddings`), không tái dùng hai cột này.

## 5-ter. B6 + B7 — embedding và hybrid search (2026-09-28)

Plan `data_pipeline_steps/step6_7_plan.md` thêm bảng `legal_chunk_embeddings`
(1289 vector `mistral-embed` 1024-dim) + HNSW + GIN trên `search_tsv`. Bản dump
`b4b5_*` ở trên không có bảng này. **Bản full ở mục 0–4 mới là bản deploy.**

### Đã kiểm chứng thế nào (bản full)

Không chỉ tạo rồi đem đi. Đã `pg_restore` vào database tạm `p029_restore_b6b7`
trên chính container này rồi so với database nguồn:

| Hạng mục | Kết quả |
|---|---|
| `alembic_version` | `0003_legal_embeddings` — khớp |
| Số dòng 4 bảng legal | 3 / 1289 / 565 / **1289** — khớp |
| md5 1289 `chunk_id` | `27837afbdc8fa5ec3308cdfa98920211` — khớp |
| **md5 toàn bộ 1289 vector** | `60e61f8afdb5c9ffa8071f7561563884` — khớp |
| md5 `chunk_id` + `content_sha256` | `70c21de5179a728a101054db748c0c62` — khớp |
| `search_tsv` NULL | 0 |
| `vector_dims(embedding) <> 1024` | 0 |

Database tạm đã bị xoá sau khi so sánh; container chỉ còn `postgres` và
`build_phase_p029`.

## 6. Lưu ý khi dùng

- **`parent_chunk_id` trong `legal_chunks` không dùng để join.** 1030/1289 giá trị là
  tham chiếu treo (có trước từ step3, giữ nguyên theo quyết định thiết kế —
  không có FK constraint). Muốn cây Điều thì dùng `article_number` /
  `clause_number` / `point_letter`, hoặc đi theo `legal_chunk_references`.
- **`target_chunk_id` NULL không phải dữ liệu hỏng** — đó là dẫn chiếu tới luật
  ngoài bộ 3 văn bản (Luật BHXH, Luật Công đoàn, số hiệu `124/2025/QH15`…).
  60/565 dòng ở trạng thái này.
- **`amended_by` NULL với 2 nghị định** là SQL NULL thật (không phải JSON `null`).
- **Bảng `legal_chunks` nặng 34 MB** dù bản dump `b4b5` cũ chỉ 290 KB (nén tốt vì
  văn bản luật lặp nhiều). Bản full ~5,4 MB vì thêm 1289 vector. Đừng ngạc nhiên.
- **`legal_chunk_embeddings` lặp lại `header_context` và `text`.** Bản sao có
  chủ đích: `search_tsv` là GENERATED ALWAYS STORED nên không thể đọc cột của
  bảng khác. FK `ON DELETE CASCADE` giữ hai bảng đồng bộ và
  `verify_embeddings.py` V2 assert từng dòng lệch 0. Chi tiết ở
  `data/chunk/CHANGELOG_B6B7.md` mục 1.1.
- **Sửa `text` một chunk thì vector cũ thành stale**, nhưng `embed_legal.py` tự
  nhận ra qua `content_sha256` và chỉ embed lại đúng dòng đó — không tốn quota cho
  1288 dòng còn lại.
- `meta` trong `legal_chunks` và `amended_by` trong `legal_documents` là JSONB; cần
  `psql` ≥ 9.6 hoặc client có hỗ trợ JSONB để hiển thị cho đẹp.
