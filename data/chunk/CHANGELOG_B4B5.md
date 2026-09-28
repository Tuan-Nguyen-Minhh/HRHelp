# CHANGELOG B4 + B5 — JSON (`data/chunk/`) → PostgreSQL

_Ngày: 2026-09-27. Plan: `data_pipeline_steps/step4_5_plan.md` REV.2._

## 0. Trạng thái

- Migration `0001_legal_schema` (nối sau `04e5c85e7957`, single head) đã áp dụng sạch.
- Seed: 3 legal_documents, 1289 legal_chunks, 565 refs.
- Verify: **70 check, 70 PASS, 0 FAIL** (`data/chunk/verify_db_014.log` — lần bàn giao sau rename).
  Mutation test: **18/18 mutation bị bắt** (`data/chunk/mutation_test_007.log`).
- V5-manual: **CHƯA ký** — xem `verify_db_manual.md`.

## 0-bis. Đổi tên `legal_*` (2026-09-28)

Bảng legal từng tên là `documents` / `chunks` / `chunk_references`, trùng tên bảng
`documents` của HR Help trên `main` (migration `04e5c85e7957`): hai head alembic,
hai class `Document` cùng `__tablename__`, metadata hỏng. Vì code legal còn trong PR
chưa merge còn bên HR đã lên `main` với ~20 bảng, bên legal đổi tên rẻ hơn:
`legal_documents` / `legal_chunks` / `legal_chunk_references`
(`LegalDocument` / `LegalChunk` / `LegalChunkReference`).

Đổi thẳng trong `0001_legal_schema.py` thay vì CREATE-rồi-RENAME vì chưa có production
DB nào chạy tên cũ — dump cũ đã bỏ, dump mới tạo lại từ JSON nguồn. Migration đồng
thời nối chuỗi `down_revision = "04e5c85e7957"` nên `alembic heads` chỉ còn một.
`alembic/env.py` giữ nguyên helper pgvector của `main`, chỉ sửa dòng import legal.
Bảng HR (`documents`, `document_chunks` với `embedding Vector(1536)` cho file upload)
giữ nguyên, không đụng. Embedding legal (B6, `mistral-embed` 1024-dim theo
`.env:26`) sẽ nằm bảng riêng, không tái dùng cột 1536-dim kia.

## 1. Migration

- Revision `0001_legal_schema`, 3 bảng: `legal_documents`, `legal_chunks`, `legal_chunk_references`.
- `UNIQUE NULLS NOT DISTINCT (source_chunk_id, target_chunk_id, target_doc, article,
  clause, point, rule)` — dùng `postgresql_nulls_not_distinct=True` (SQLAlchemy 2.1.1
  nhận kwarg này dù không nằm trong `Index.__init__` signature).
- Index ngược `ix_legal_chunk_references_target_source (target_chunk_id, source_chunk_id)`
  cũng `NULLS NOT DISTINCT`.
- CHECK: `ck_legal_documents_status`, `ck_legal_chunks_chunk_level`, `ck_legal_chunk_references_confidence`
  (HIGH|LOW), `ck_legal_chunk_references_needs_reason` (BOUNDARY|UNRESOLVED).
- `parent_chunk_id` là TEXT **không FK** (thiết kế gốc, xem [V3-ter]).
- `legal_documents.doc_code`: chỉ **một** unique index (`ix_legal_documents_doc_code`). Bản đầu
  tạo cả UNIQUE constraint + unique index → 2 index trùng nhau trên 1 cột, đã bỏ.

## 2. B4 — Documents + Chunks

| document_id | doc_code | status | article_count | chunk_count |
|---|---|---|---|---|
| 18/VBHN-VPQH | BLLD | PARTIALLY_AMENDED | 220 | 381 |
| 145/2020/NĐ-CP | ND145_2020 | ACTIVE | 115 | 377 |
| 283/2026/NĐ-CP | ND283_2026 | ACTIVE | 68 | 531 |

- `amended_by` BLLD = 5 footnote (key 2,3,4,5,6) từ `document_tree_BLLD.json`.
  *Lưu ý: plan mục 2.3 ghi "6 footnote" nhưng `document_tree_BLLD.json` thực tế có
  5 mục (footnote 1 không dùng hệ `[[n]]`). Đã theo dữ liệu thật.*
- `chunk_count` / `article_count` **tính lại từ bảng `legal_chunks`**, không hard-code.
- Transaction **riêng cho từng chunk-file** (plan 2.3), batch 500.
- `updated_at` được set thủ công (`sa.func.now()`) trong mọi `on_conflict_do_update`.
  `onupdate=func.now()` của ORM **không** áp dụng cho `pg_insert().on_conflict_do_update()`
  — bản đầu để sót, đã sửa.

## 3. B5 — Chunk References

Tổng **565** = BLLD 125 + NĐ145 233 + NĐ283 207.

### 3.1 Sửa bug P0 — `build_chunk_lookup` ghi đè key theo level

Bản đầu dùng một dict phẳng và ghi **mọi** chunk vào cả key 2 và key 3:

```python
lookup[(doc, art)]        = cid   # mọi chunk, kể cả CLAUSE/POINT
lookup[(doc, art, cl)]    = cid   # mọi chunk có clause, kể cả POINT
```

Chunk CLAUSE/POINT đứng sau trong file JSON đè lên key của chunk ARTICLE.
Đo được: **144/403** key 2-term trỏ sai level, **66/691** key 3-term trỏ sai level.
Hệ quả trên dữ liệu thật: **105/565 refs (18,6%)** có `target_chunk_id` sai level —
86 refs cấp Điều trỏ vào một khoản bất kỳ, 19 refs cấp khoản trỏ vào một điểm bất kỳ.
Giá trị bị chọn phụ thuộc thứ tự file, không ổn định.

Cách sửa: `ChunkIndex` tách namespace theo level (`by_clause`, `by_point`,
`article_rep`), mỗi level chỉ nhận chunk của chính nó. `article_rep` chọn tất định:
chunk ARTICLE nếu có, không thì chunk có `clause_number` nhỏ nhất.

### 3.2 Chính sách resolve (tất định, không bịa)

`POINT khớp letter → CLAUSE khớp number → ARTICLE` (plan 3.5). Khi granularity
yêu cầu không có chunk tương ứng, fallback về **chunk đại diện của Điều** thay vì
một chunk ngẫu nhiên. Phân bố thực tế:

| cách resolve | số refs |
|---|---|
| `point` — khớp điểm | 19 |
| `clause` — khớp khoản | 186 |
| `article` — khớp Điều | 192 |
| `fallback` — về chunk đại diện Điều | 108 |
| `external` — luật ngoài allowlist, target NULL | 60 |

`fallback` xảy ra khi văn bản hợp nhất đã cấu trúc lại (ví dụ Điều bị tách hết thành
khoản nên không còn chunk cấp Điều, hoặc điểm/khoản được dẫn không tồn tại trong bản
hợp nhất). 108 ca được in mẫu ra log seed. Không thêm cột granularity vì
`legal_chunk_references` không có cột đó theo plan; tham chiếu logic vẫn đọc được qua
`target_doc` / `article` / `clause` / `point`.

### 3.3 needs_review

- `needs_review` = `needs_reason IS NOT NULL` (một nguồn sự thật, có V4 kiểm tra).
- `UNRESOLVED` thắng `BOUNDARY` nếu cùng xảy ra.
- **BOUNDARY = 3** (3 LOW `BOUNDARY_CHECK` đã biết), **UNRESOLVED = 0** (mọi
  `target_doc` ngoài bộ 3 đều thuộc allowlist tên luật hoặc regex số hiệu).
- B5 chạy trong **1 transaction** (DELETE + insert), crash giữa chừng rollback hết.

## 4. Verify — siết lại đúng plan

Bản đầu có 4 chỗ "PASS giả", đã sửa:

| Mục | Bản đầu | Nay |
|---|---|---|
| V1 | `record(..., True, ...)` — không bao giờ so head | resolve head từ `ScriptDirectory`, so `alembic_version`; assert `NULLS NOT DISTINCT` trên constraint **và** trên index ngược; assert `doc_code` chỉ có **1** unique index; bỏ `return` sớm khi lỗi |
| V5-auto | 5 case chỉ check `found=True` | assert **giá trị cứng** (xem bên dưới) |
| V3-bis | chỉ in "Sampled 30" | in **đủ 30 ID** để tái lập, + assert `is_quoted_external_text` = 20 |
| V7 | in hash, không so gì | so với **manifest đã pin** `data/chunk/source_manifest.json` + so trước/sau trong lần chạy |

Thêm mới: V4 `needs_review` nhất quán với `needs_reason`; V6 chạy **CLI thật**
(`subprocess` gọi `scripts/seed_legal.py`) thay vì gọi hàm in-process, và so cả
**fingerprint md5** của toàn bộ 565 refs chứ không chỉ count.

### 4.1 V5-auto — 5 case assert cứng

| Case | Assert |
|---|---|
| 1 | `ND283 A044:C01` → đúng 1 dòng, `target_doc='Luật Bảo hiểm xã hội'`, `article=28`, `target_chunk_id IS NULL` |
| 2 | inbound tới BLLD Đ169 từ NĐ145 **đúng 2 source**: `ND145_2020:CIII:M02:A008:C01`, `ND145_2020:CX:M00:A089:C01:P-d1` |
| 3 | `A219:C02` có **2 hướng** dẫn chiếu: BHXH Đ2 khoản 1 điểm e (target NULL) + BLLD Đ169 khoản {2,3} → target `BLLD:CXII:M00:A169:C02`/`C03`. Ngược lại mỗi target nhận ≥2 source khác nhau (kiểm tra index ngược) |
| 4 | `ND145 A070:C03` → đúng 1 dòng HIGH, target **ghim cứng** `BLLD:CVIII:M01:A122:C01` (CLAUSE) |
| 5 | `ND283 A066` LIST_EXPANSION self → articles **đúng** `[7, 14]`, target non-null |

**Hai điểm plan cần chốt lại, đã ghi lại đây:**

- *Case 3 "2 chiều"*: dữ liệu **không có** inbound edge nào tới BLLD Đ219 (đã kiểm
  `references pointing at article 219` = rỗng). Nên "2 chiều" được hiểu là **2 hướng
  dẫn chiếu** (luật ngoài + văn bản trong bộ), khớp `CHANGELOG.md` mục 1. Nếu ý plan
  là edge hai chiều thì đó là khiếm khuyết dữ liệu B5, cần xử lý ở step3, không phải ở đây.
- *Case 4*: ref mang `point='c'` nhưng BLLD Đ122 trong bản hợp nhất **chỉ có chunk
  CLAUSE** (C01–C06, không có điểm) → fallback về khoản 1. Target được ghim đúng để
  mọi thay đổi hành vi fallback sau này đều bị bắt.

### 4.2 V7 — manifest

V7 trước đây chỉ so hash trong một lần chạy, nên **file nguồn đã hỏng từ trước vẫn
PASS**. Nay có `data/chunk/source_manifest.json` ghim sha256 của 6 file nguồn đã
đóng băng; V7 assert khớp manifest, và manifest thiếu thì FAIL (bắt buộc phải có).
Cập nhật có chủ đích: `python scripts/verify_db.py --write-manifest`.

### 4.3 Chứng minh check không rỗng (mutation test)

`scripts/mutation_test.py` phá dữ liệu có chủ đích rồi đòi đúng check phải FAIL.
**18/18 mutation đều bị bắt.**

Các lần chạy đầu không đạt đã dẫn tới ba sửa thật:

- **V7** (xem 4.2) — lỗi thiết kế của check, đã sửa bằng manifest.
- **`amended_by` JSON `null`** (xem 4.4) — phát hiện khi rà trạng thái cuối, thêm 3
  check V2 và 2 mutation.
- **CRLF trong chính mutation test** — `write_text` trên Windows dịch `\n` → `\r\n`,
  làm hỏng file 743 KB mà script sinh ra để kiểm tra. Phát hiện nhờ dòng tự assert
  trạng thái sau khôi phục; đã sửa bằng `write_bytes`.

Ba lần "MISSED" còn lại là mutation sai của tôi, không phải bug: chọn chunk ngoài
sample 30 của V3-bis; chọn chunk vốn đã có parent treo; và khai báo sai tên check kỳ
vọng cho mutation `amended_by` (check thật có bắt, chỉ là harness khai sai tên).

Chi tiết: `data/chunk/mutation_test_report.md`.
Log: `mutation_test_001.log` … `mutation_test_005.log` (giữ hết, kể cả lần FAIL).

### 4.4 Sửa thêm: `amended_by` là JSON `null` chứ không phải SQL NULL

Rà soát trạng thái cuối phát hiện `legal_documents.amended_by` của NĐ145 và NĐ283 **không
phải SQL NULL** mà là JSON `null` nằm bên trong JSONB (`jsonb_typeof` = `'null'`, còn
`amended_by IS NULL` = false). Nguyên nhân: SQLAlchemy khai `JSONB` không có
`none_as_null`, nên Python `None` được serialize thành JSON `null` thay vì SQL NULL.
Hệ quả: mọi truy vấn kiểu `WHERE amended_by IS NULL` đều không match được 2 văn bản
này.

Đã sửa:

- model: `JSONB(none_as_null=True)` cho cả `legal_documents.amended_by` và `legal_chunks.meta`
- seed: bỏ hẳn `amended_by=None` khỏi giá trị insert, và **luôn** ghi lại `amended_by`
  (kể cả với `{}` → SQL NULL) để giá trị cũ không sống sót qua lần seed sau
- verify: thêm `V2.amended_by_is_object_or_null` + `V2.ND145_2020.amended_by_sql_null`
  + `V2.ND283_2026.amended_by_sql_null`, hỏi thẳng DB bằng `jsonb_typeof` chứ không
  tin vào ORM

## 5. Drift đã biết (không sửa, ghi nhận)

- **BLLD Điều 54 khoản 3**: `ND145 A114 P-c` trỏ khoản 3 không tồn tại trong BLLD hợp
  nhất 2019 (Đ54 chỉ có khoản 1–2). Giữ HIGH vì định danh luật đúng; giờ resolve về
  chunk đại diện Điều, có log.
- **BLLD Điều 122**: 9 ref từ NĐ145 mang `point='c'` nhưng Đ122 không có chunk điểm →
  fallback về `BLLD:CVIII:M01:A122:C01`.
- **parent treo 1030**: `parent_chunk_id` không có giá trị nào resolve được. Đây là
  thiết kế gốc của `chunking_engine._make_chunk` (luôn trỏ về ARTICLE id), tồn tại
  trước mọi fix, giữ nguyên để không đổi `chunk_id` scheme.

## 5-bis. Thay đổi `.gitignore`

`data/*` khiến toàn bộ artifact B4/B5 bị bỏ qua, **kể cả `source_manifest.json` mà
V7 bắt buộc phải có** — clone mới sẽ FAIL ngay ở `V7.manifest_exists`. Đã thêm
exception cho đúng 6 nhóm file bàn giao:

```
!data/chunk/
data/chunk/*
!data/chunk/source_manifest.json
!data/chunk/CHANGELOG_B4B5.md
!data/chunk/mutation_test_report.md
!data/chunk/verify_db_manual.md
!data/chunk/verify_db_*.log      # phải nằm DƯỚI rule `*.log`
!data/chunk/mutation_test_*.log  # vì git lấy pattern khớp cuối cùng
```

File JSON đầu vào đóng băng (743 KB–1,2 MB) vẫn **không** được commit.

## 6. Artifacts

- `alembic/versions/0001_legal_schema.py` — migration
- `src/models/legal.py` — model (có CHECK khớp migration)
- `scripts/seed_legal.py` — seed B4 + B5
- `scripts/verify_db.py` — verify V1–V7 (70 check)
- `scripts/mutation_test.py` — negative control, 18 mutation
- `data/chunk/source_manifest.json` — sha256 ghim của 6 file nguồn
- `data/chunk/CHANGELOG_B4B5.md` — file này
- `data/chunk/verify_db_*.log` — mọi lần chạy, đánh số thứ tự, kể cả FAIL
- `data/chunk/mutation_test_report.md` — bằng chứng check không rỗng
- `data/chunk/verify_db_manual.md` — V5-manual, **chờ ký**

## 7. Ngoài phạm vi

Không sửa text/metadata chunk; không embed (B6); không Qdrant/BM25 (B7); không đổi
`chunk_id` scheme; không sửa công thức lương.
