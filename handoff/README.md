# Handoff — dữ liệu B4 + B5

_Ngày: 2026-09-27. Nguồn: PostgreSQL 16.15 + pgvector 0.8.6, container `p-029-db-1`._

## 1. Có gì trong thư mục này

| File | Kích thước | Dùng để |
|---|---|---|
| `b4b5_build_phase_p029.dump` | 290 KB | **Dùng để import** — định dạng custom của `pg_dump`, nén |
| `b4b5_build_phase_p029.dump.sha256` | — | Kiểm tra file còn nguyên (toàn bộ `handoff/` đã commit vào git) |
| `b4b5_build_phase_p029.sql` | 2,4 MB | SQL thuần, để đọc/diff/review, không dùng để import |
| `source_manifest.json` | — | sha256 của 6 file JSON nguồn mà B4/B5 đọc vào |

Cả thư mục `handoff/` (2,57 MB) đã nằm trong git, clone về là có đủ — không cần
chuyển file qua Zalo/Drive.

## 2. Import vào máy mới

```bash
# 1. Bật Postgres (đã có trong docker-compose.yml, service tên `db`)
docker compose up -d db

# 2. Kiểm tra file dump còn nguyên
#    Windows:  certutil -hashfile b4b5_build_phase_p029.dump SHA256
#    Linux/mac:  shasum -a 256 b4b5_build_phase_p029.dump
#    So với:     f4ff3aa890cdffeaaa1385be48a032bb61b3d82138f25dee8f07b3e13e69fcfa
#    Git đã bảo toàn file nên bước này là tùy chọn; hữu ích khi file bị tải
#    lại qua trung gian hoặc khi muốn chắc chắn bản dump còn nguyên.

# 3. Import
docker cp b4b5_build_phase_p029.dump p-029-db-1:/tmp/b4b5.dump
docker exec p-029-db-1 pg_restore \
  -U postgres -d build_phase_p029 \
  --no-owner --no-privileges --clean --if-exists \
  /tmp/b4b5.dump
```

**Không cần chạy Alembic** — dump đã chứa cả bảng `alembic_version` với giá trị
`0001_legal_schema`, và cả extension `vector` sẽ được tạo lại nếu máy mới thiếu
(yêu cầu image Postgres có pgvector, giống `p029-postgres`).

Nếu muốn nạp từ bản SQL thuần thay vì file `.dump`:

```bash
docker cp b4b5_build_phase_p029.sql p-029-db-1:/tmp/b4b5.sql
docker exec p-029-db-1 psql -U postgres -d build_phase_p029 -f /tmp/b4b5.sql
```

## 3. Nội dung

| Bảng | Số dòng | Ý nghĩa |
|---|---|---|
| `legal_documents` | 3 | 3 văn bản luật + hiệu lực + footnote sửa đổi |
| `legal_chunks` | 1289 | Nội dung luật đã chia nhỏ (Điều / khoản / điểm) |
| `legal_chunk_references` | 565 | Đồ thị dẫn chiếu nối 3 văn bản |
| `alembic_version` | 1 | Phiên bản migration đã áp dụng |

Chi tiết hơn: `data/chunk/CHANGELOG_B4B5.md`.

## 4. Sau khi import phải chạy lại verify

Không tin lời tôi, tự kiểm. Cần `data/chunk/*.json` (6 file) và
`data/chunk/source_manifest.json` trong repo:

```bash
python -m alembic upgrade head      # no-op, dump đã ở head
python scripts/verify_db.py         # 70 check
```

Kết quả mong đợi: `Total: 70 PASS, 0 FAIL`.

## 5. Đã kiểm chứng thế nào

Dump **không** chỉ được tạo rồi đem đi. Nó đã được restore vào một database tạm
`p029_restore_test` trên chính container này, rồi so sánh với database nguồn:

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

Bảng legal (B6) sẽ có bảng embedding riêng, không tái dùng hai cột này.

## 6. Lưu ý khi dùng

- **`parent_chunk_id` trong `legal_chunks` không dùng để join.** 1030/1289 giá trị là
  tham chiếu treo (có trước từ step3, giữ nguyên theo quyết định thiết kế —
  không có FK constraint). Muốn cây Điều thì dùng `article_number` /
  `clause_number` / `point_letter`, hoặc đi theo `legal_chunk_references`.
- **`target_chunk_id` NULL không phải dữ liệu hỏng** — đó là dẫn chiếu tới luật
  ngoài bộ 3 văn bản (Luật BHXH, Luật Công đoàn, số hiệu `124/2025/QH15`…).
  60/565 dòng ở trạng thái này.
- **`amended_by` NULL với 2 nghị định** là SQL NULL thật (không phải JSON `null`).
- **Bảng `legal_chunks` nặng 34 MB** dù file dump chỉ 290 KB (nén tốt vì văn bản luật
  lặp nhiều). Đừng ngạc nhiên.
- `meta` trong `legal_chunks` và `amended_by` trong `legal_documents` là JSONB; cần
  `psql` ≥ 9.6 hoặc client có hỗ trợ JSONB để hiển thị cho đẹp.
