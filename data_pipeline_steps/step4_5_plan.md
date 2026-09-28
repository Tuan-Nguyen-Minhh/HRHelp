# PLAN B4 + B5: JSON (`data/chunk/`) → PostgreSQL (documents + graph) — REV.2

## 0. Mục tiêu & nguyên tắc

- Nạp 3 văn bản đã final (BLLD 381 / NĐ145 377 / NĐ283 531 chunk, tổng 1289) vào
  Postgres local (`p-029-db-1`, PostgreSQL 16.15 + pgvector 0.8.6 — đã xác nhận từ
  container log, đủ điều kiện dùng `NULLS NOT DISTINCT` ≥ PG15) làm source of truth.
- B4 = metadata & hiệu lực (`documents` + metadata chunk). B5 = graph dẫn chiếu
  (`chunk_references`). Không sửa text chunk. Không embed/vector (B6/B7).
- Idempotent + reconciliation trong transaction: chạy lại không trùng, rule đổi thì
  rác cũ bị xóa cùng 1 transaction với insert mới.

## 1. Đầu vào (đóng băng)

- `data/chunk/chunks_*.json`, `document_tree_*.json`, `step3_stats.json`,
  `validation_report.md`, `low_confidence_refs.json` (3 LOW BOUNDARY).
- `.env`: `DB_USER=postgres`, `DB_PASSWORD=postgres`, `DB_HOST=localhost`,
  `DB_PORT=5432`, `DB_NAME=build_phase_p029`. Code chạy ngoài docker → `localhost`.

## 2. B4 — việc phải làm (chốt schema trước migrate)

1. Model mới `src/models/legal.py` (+ `created_at/updated_at` cả 3 bảng):
   - `Document`: `document_id` PK text (giữ dấu `/`, API sau encode khi đưa vào
     URL), `doc_code` unique, `document_type/form/title`, `status` enum đủ 4
     (`ACTIVE` | `PARTIALLY_AMENDED` | `INACTIVE` | `SUPERSEDED`) — hiện chỉ dùng
     2 giá trị đầu, `amended_by` JSON nullable, `article_count`, `chunk_count`.
   - `Chunk`: `chunk_id` PK, `document_id` FK → documents (enforced),
     `parent_chunk_id` **TEXT thường, KHÔNG FK constraint** (giá trị treo có trước
     — chỉ lưu tham chiếu, đếm ở [V3-ter]), `header_context`, `text`,
     **cột riêng index**: `article_number`, `clause_number` nullable,
     `point_letter` nullable, `chunk_level`, `document_id`;
     **cột `meta JSONB`**: toàn bộ metadata còn lại (chapter/section/title,
     chapeau, penalty, token, flags, quoted…). Chốt: filter B7 dùng cột riêng,
     audit chi tiết đọc `meta` (không đổi ý sau migrate).
2. Alembic revision autogenerate từ `Base.metadata`, review SQL bằng tay rồi mới
   `alembic upgrade head` lên `p-029-db-1`.
3. Seed `scripts/seed_legal.py` (B4 phần):
   - Upsert documents: BLLD = PARTIALLY_AMENDED (6 footnote), 220;
     NĐ145 ACTIVE 115; NĐ283 ACTIVE 68. `amended_by` từ `document_tree.footnotes`.
   - Bulk insert 1289 chunk (batch 500, transaction/chunk-file). `chunk_count` /
     `article_count` trên `documents` KHÔNG hard-code: tính lại bằng COUNT(*) thực
     tế từ bảng `chunks` sau khi insert xong (cùng transaction cuối), upsert ngược
     vào documents.

## 3. B5 — việc phải làm

4. Model `ChunkReference` — CHỐT (không để code tự quyết):
   - `ref_id` SERIAL PK (surrogate, vì `target_chunk_id` nullable cho luật ngoài).
   - `source_chunk_id` FK → chunks (enforced), `target_chunk_id` FK nullable →
     chunks (external = NULL), `target_doc`, `article`, `clause` nullable,
     `point` nullable, `rule`, `confidence`, `needs_review` bool default false,
     `needs_reason` text (`BOUNDARY` | `UNRESOLVED`).
   - **Một** UNIQUE duy nhất:
     `UNIQUE (source_chunk_id, target_chunk_id, target_doc, article, clause,
     point, rule) NULLS NOT DISTINCT` (PostgreSQL 16 đã xác nhận — KHÔNG dùng
     thêm partial index riêng, tránh dư thừa; 2 ref cùng target Điều nhưng khác
     khoản/điểm không ghi đè nhau).
   - Index ngược `(target_chunk_id, source_chunk_id)` (NULLS NOT DISTINCT).
5. Resolve `target_chunk_id` + phân loại internal/external có kiểm chứng:
   - Cùng/khác doc trong bộ 3: POINT khớp letter → CLAUSE khớp number → ARTICLE.
   - External **allowlist** (BHXH, An toàn VSLĐ, NLD NN theo HĐ, Công đoàn, XLVPHC,
     số hiệu regex `\d{2,3}/20\d{2}/[A-ZĐ0-9-]+`…): thuộc list mới được NULL;
     tên lạ ngoài list → `needs_review=true`, `needs_reason='UNRESOLVED'`,
     `target_chunk_id=NULL`, vào báo cáo (V4-bis).
   - LOW `BOUNDARY_CHECK` (đúng 3 case) → `needs_review=true`, `needs_reason='BOUNDARY'`.
6. Seed B5 trong `scripts/seed_legal.py`, **1 transaction duy nhất**:
   `DELETE FROM chunk_references` (dev truncate-and-reseed) rồi bulk insert set
   mới — crash giữa chừng rollback hết, không dở dang.

## 4. Vòng lặp VERIFY (sau MỖI lần sửa, chưa đạt hết quay lại từ B4.2)

`scripts/verify_db.py` chỉ tự động V1–V4ter, V5-auto, V6–V7 và in PASS/FAIL.
Review tay là bước ký riêng ngoài loop (xem V5-manual). Dừng auto-loop khi tất cả
mục auto đạt cùng 1 lần chạy; nhận nghiệm cuối khi có thêm sign-off V5-manual.
Phạm vi quay lại khi FAIL: lỗi allowlist mới (V4-bis UNRESOLVED, chỉ thêm tên luật
ngoài vào list ở B5) thì **chỉ chạy lại từ B5** (seed refs + V4/V5/V6), không đụng
model/migration B4; mọi lỗi còn lại quay lại từ B4.2. Ghi rõ phạm vi vào changelog.

- [V1] Kết nối + migration: `alembic current` = head; đủ 3 bảng; ext `vector` có.
- [V2] Documents: đúng 3 dòng; article_count 220/115/68; BLLD PARTIALLY_AMENDED,
  2 NĐ ACTIVE; `amended_by` BLLD non-null; **chéo**: `documents.chunk_count` phải
  bằng COUNT(*) thực tế trong `chunks` theo từng doc (381/377/531),
  `article_count` bằng COUNT(DISTINCT article_number) — chống nói dối khi crash
  giữa batch rồi resume.
- [V3] Chunks: **cứng** 381/377/531 (tổng 1289, không ±); 0 rỗng; 0 trùng id;
  cover đủ Điều.
- [V3-bis] Cột đặc thù: seed cố định `seed=42`, random 30 chunk ID (in đủ 30 ID
  vào log để tái lập), so JSON↔DB khớp 100%: penalty_min/max/subject,
  anomaly_flags, has_chapeau/chapeau_text, is_quoted_external_text (BLLD Điều 219
  đúng 20 True), clause_number + implicit.
- [V3-ter] Parent treo: `SELECT count(*) FROM chunks WHERE parent_chunk_id IS NOT
  NULL AND parent_chunk_id NOT IN (SELECT chunk_id FROM chunks)` phải **bằng đúng
  số đếm từ JSON nguồn** (tính cùng công thức trên 3 `chunks_*.json`, in cả 2 số
  ra log; kỳ vọng ~1030 theo deep sweep — nếu lệch là FAIL, không giải trình miệng).
- [V4] Refs: **cứng** tổng 565 = 125 + 233 + 207 (không ±, không "giải trình");
  `target_doc` validate bằng regex số hiệu hoặc tên trong allowlist (bỏ magic
  number độ dài); internal có article tồn tại.
- [V4-bis] UNRESOLVED = 0 (`needs_reason='UNRESOLVED'`).
- [V4-ter] Needs_review tổng hợp: `BOUNDARY` đúng 3 AND `UNRESOLVED` = 0
  (phân biệt fix-logic vs chấp nhận được).
- [V5-auto] Traverse cố định 5 case (assert đáp án cứng trong script):
  NĐ283 A044:C01→BHXH Đ28 (NULL); BLLD Đ169 có inbound NĐ145; A219:C02 2 chiều;
  A070:C03→Đ122 HIGH; A066 LIST self Đ7/14.
- [V5-manual] (ngoài auto-loop, sign-off riêng): random `seed=42`, 5–10%/rule type,
  checklist tay ghi vào `verify_db_manual.md` (người review ký + ngày). Auto-loop
  không chờ bước này để PASS, nhưng nhận nghiệm cuối yêu cầu cả hai.
- [V6] Idempotent + reconciliation: seed 2 lần, count V2–V4ter không đổi, 0 rác cũ.
- [V7] Source untouched: `data/chunk/*.json` sha256 trước/sau giống nhau.

## 5. Output cuối

1. Migration `alembic/versions/*.py` + DB đã migrate.
2. `scripts/seed_legal.py`, `scripts/verify_db.py` (chạy từ `.venv`).
3. `data/chunk/CHANGELOG_B4B5.md` + `data/chunk/verify_db_*.log` (giữ **mọi** lần
   chạy, kể cả FAIL, đánh số thứ tự) + `verify_db_manual.md` (sign-off tay).
4. Phụ lục drift đã biết (BLLD Điều 54 khoản 3) + parent treo (TEXT, không FK).

## 6. Không làm

- Không sửa text/metadata chunk; không embed (B6), không Qdrant/BM25 (B7);
  không sửa công thức lương; không đổi `chunk_id` scheme.
