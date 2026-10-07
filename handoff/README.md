# Handoff — snapshot database (bản full + lịch sử)

_Ngày: 2026-09-27 (B4/B5), bổ sung 2026-09-28 (B6/B7), đổi tên dump `b6b7_*` → `full_*`
2026-09-29, bổ sung tài liệu nội bộ NQCT + fix qualifier trần 2026-10-01 (xem
`data/chunk/CHANGELOG.md` mục mới nhất). Nguồn: PostgreSQL 16.15 + pgvector 0.8.6, container `p-029-db-1`._

## 0. Dùng bản nào — đọc trước

- **Máy mới / deploy: chỉ dùng `full_build_phase_p029.dump`.** Đó là snapshot
  **full** của cả database — đủ 4 bảng legal
  (documents 4 / chunks 1377 / references 599 / **embeddings 1377**).
- `b4b5_*` là **lịch sử**, giữ lại để biết B4/B5 bàn giao cái gì. Nó **thiếu
  bảng vector** — import bản này thì `document_chunks` không có embedding nên
  nhánh `similarity` của cite trả về rỗng. Đừng dùng để deploy.

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
Xong kiểm bằng các câu SQL ở mục 4.

Làm tay (khi script không chạy được, VD container tên khác — kiểm tra bằng
`docker ps` rồi thay tên):

```powershell
certutil -hashfile handoff\full_build_phase_p029.dump SHA256
# phải khớp handoff\full_build_phase_p029.dump.sha256:
# 9DF9D466B8F0348BF2708A475905FE4AC5505BA17A7D44C1A9DB77C729EAF8FF
docker cp handoff\full_build_phase_p029.dump p-029-db-1:/tmp/full.dump
docker exec p-029-db-1 pg_restore -U postgres -d build_phase_p029 --no-owner --no-privileges --clean --if-exists /tmp/full.dump
```
```

**Không cần chạy Alembic** — dump đã chứa bảng `alembic_version` với giá trị
`0011_chunk_references`.

> ⚠️ **`pg_dump` KHÔNG tạo lại extension.** `vector` (pgvector) và `btree_gist`
> (cho `ExcludeConstraint` uuid của `policy_versions`) phải có sẵn ở database
> đích trước khi restore. Thiếu `vector` → `document_chunks.embedding vector(1024)`
> không tạo được → 16 lỗi FK liên tiếp, và `pg_restore` **vẫn exit 0** trong khi
> báo `errors ignored: 17`.
>
> `scripts/restore_handoff.ps1` đã tạo 2 extension đó ở bước 3 và kiểm tra
> exit code của `pg_restore`. Nếu bạn restore thủ công, làm y hệt — và **đếm bảng
> sau khi restore** (kỳ vọng 16), đừng tin dòng "Restore xong".
>
> Image Postgres phải có pgvector, giống `p029-postgres`.

## 3. Nội dung (bản full)

| Bảng | Số dòng | Ý nghĩa |
|---|---|---|
| `policies` | 4 | 3 văn bản luật (BLLĐ 2019, NĐ 145/2020, NĐ 283/2026) + Nội quy HRCorp (`INTERNAL_RULE`) |
| `policy_versions` | 4 | Thời gian hiệu lực từng văn bản (bảo vệ bằng ExcludeConstraint) |
| `documents` | 4 | Bản ghi tài liệu nguồn (`ingest_status='EMBEDDED'`) |
| `document_chunks` | 1405 | 1405 chunks đầy đủ text, vector 1024-dim, và search_tsv (GIN) |
| `chunk_references` | 615 | **Đồ thị dẫn chiếu trên corpus sống.** FK → `document_chunks.id`. 63 dòng đích NULL = luật ngoài bộ 3 |
| `legal_documents` | 4 | 3 văn bản luật + 1 nội quy (`NOI_QUY`/`VAN_BAN_NOI_BO`) + footnote sửa đổi |
| `legal_chunks` | 1405 | Nội dung đã chia nhỏ (Điều / khoản / điểm), 116 chunk NQCT đánh số tuần tự 1–100 |
| `legal_chunk_references` | 615 | Đồ thị dẫn chiếu (NQCT: 21 EXPLICIT + 15 EXPLICIT_SELF + 8 LIST_EXPANSION + 6 DEFAULT_SELF, 0 BOUNDARY; BOUNDARY toàn corpus = 3) |
| `legal_chunk_embeddings` | 1405 | Vector `mistral-embed` 1024-dim + tsvector BM25 (B6/B7) |
| `roles` / `permissions` | 5 / 18 | Seed RBAC — thiếu thì app không đăng nhập được |
| `users` | 5 | Tài khoản demo từ `scripts/seed_demo_users.py` (kèm hash mật khẩu) |
| `alembic_version` | 1 | Phiên bản migration đã áp dụng (`0011_chunk_references`) |

> **Bản này chỉ chứa corpus + seed** — 16 bảng. 21 bảng vận hành (`cases`,
> `messages`, `recommendations`, `agent_runs`, `audit_logs`, …) cố ý **không**
> đưa vào dump; đó là dữ liệu demo cục bộ. `legal_*` vẫn có trong dump làm bản
> dựng lại corpus.
>
> **Số trên lấy từ `scripts/corpus_expectations.py`** (tự dẫn từ
> `data/chunk/chunks_*.json`), không gõ tay. Chạy
> `python scripts/corpus_expectations.py` để in lại bất cứ lúc nào.
> `full_build_phase_p029.dump` đã refresh ở head `0011_chunk_references`
> và có đầy đủ 100 Điều NQCT — 16/16 bảng, `document_chunks` 1405, `chunk_references` 615,
> `legal_chunk_embeddings` 1405, 0 lỗi.

Chi tiết B4/B5: `data/chunk/CHANGELOG_B4B5.md`. Chi tiết B6/B7:
`data/chunk/CHANGELOG_B6B7.md`.

## 4. Sau khi import phải tự kiểm

> **Cập nhật 2026-10-06:** `scripts/verify_db.py`, `scripts/verify_embeddings.py`
> và `scripts/mutation_test.py` đã bị gỡ khỏi repo (cùng `src/services/hybrid_search.py`
> và bộ kết quả `eval/results/retrieval_eval_*`). Lý do: chúng đo một engine mà
> agent không gọi, và số liệu đó không kiểm chứng được nên không nên đưa vào báo cáo.
> Các mục lịch sử 4-bis / 5 / 5-ter bên dưới **giữ nguyên số cũ theo đúng ngày
> chúng được chạy** — đó là bản ghi, không phải số hiện tại.

Không tin lời tôi, tự kiểm bằng SQL trên database vừa import:

```sql
-- Kỳ vọng: 16 — nếu thiếu, restore đã hỏng dù script in "Restore xong"
SELECT count(*) FROM pg_tables WHERE schemaname = 'public';

-- Kỳ vọng: 4 / 1405 / 615 / 615 / 1405 / 1405
SELECT 'legal_documents' t, count(*) FROM legal_documents
UNION ALL SELECT 'legal_chunks', count(*) FROM legal_chunks
UNION ALL SELECT 'legal_chunk_references', count(*) FROM legal_chunk_references
UNION ALL SELECT 'chunk_references', count(*) FROM chunk_references
UNION ALL SELECT 'legal_chunk_embeddings', count(*) FROM legal_chunk_embeddings
UNION ALL SELECT 'document_chunks', count(*) FROM document_chunks;

-- Kỳ vọng: 1 dòng, version_num = 0011_chunk_references
SELECT * FROM alembic_version;

-- Kỳ vọng: 0 — đồ thị không có cạnh nào trỏ tới chunk không tồn tại
SELECT count(*) FROM chunk_references r
LEFT JOIN document_chunks d ON d.id = r.source_chunk_id WHERE d.id IS NULL;

-- Kỳ vọng: 1405 dòng đều có vector đúng 1024 chiều, 0 NULL
SELECT count(*) FILTER (WHERE embedding IS NULL) AS null_vec,
       count(*) FILTER (WHERE vector_dims(embedding) <> 1024) AS wrong_dim
FROM legal_chunk_embeddings;

-- Kỳ vọng: 0 — vector phải khớp sha256 của text hiện tại
SELECT count(*) AS stale
FROM legal_chunk_embeddings e JOIN legal_chunks c USING (chunk_id)
WHERE e.content_sha256 <> encode(sha256(convert_to(c.text, 'UTF8')), 'hex');

-- Kỳ vọng: 1405 — đây mới là bảng cite đọc lúc runtime
SELECT count(*) FROM document_chunks dc
JOIN documents d ON d.id = dc.document_id
JOIN policy_versions pv ON pv.id = d.policy_version_id
JOIN policies p ON p.id = pv.policy_id
WHERE p.is_active AND d.ingest_status IN ('CHUNKED','EMBEDDED');
```

Số kỳ vọng từ `python scripts/corpus_expectations.py` (tự dẫn từ
`data/chunk/chunks_*.json`, không gõ tay).

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
