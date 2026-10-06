# Runbook — Có DB đầy đủ trên local (P-029)

_Mục tiêu: agent khác đọc file này và chạy lệnh để có DB đầy đủ.
Nhánh: `tuan_data_pipeline`. Shell dưới đây là PowerShell trên Windows._

## 0. Chuẩn bị (1 lần)

```powershell
git checkout tuan_data_pipeline; git pull
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # điền DB_* và MISTRAL_API_KEY
docker compose up -d db  # chờ healthy: docker ps
```

## 1. Đường nhanh — nạp dump có sẵn (khuyên dùng)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore_handoff.ps1
```

Xong thì kiểm bằng các câu SQL ở mục 4 của `handoff/README.md`
(kỳ vọng `4 / 1377 / 599 / 1377 / 1377`, 0 embedding NULL).
Không chạy thêm seed gì.
Tên container khác `p-029-db-1` thì truyền `-Container <tên> -DbName <tên>` (xem tên bằng `docker ps`).

## 2. Đường đầy đủ — build DB từ nguồn (khi sửa/nguồn đổi/thêm văn bản)

Chạy đúng thứ tự, dừng ngay nếu bước nào đỏ:

```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe data_pipeline_steps\step2\step2_preprocessing.py
.\.venv\Scripts\python.exe -m data_pipeline_steps.step3.run_step3
.\.venv\Scripts\python.exe scripts\seed_legal.py
.\.venv\Scripts\python.exe scripts\embed_legal.py
.\.venv\Scripts\python.exe scripts\seed_hr_from_legal.py
.\.venv\Scripts\python.exe scripts\copy_chunk_references.py   # đồ thị dẫn chiếu
.\.venv\Scripts\python.exe -m pytest -q           # 32 passed
```

> ⚠️ **Thứ tự bắt buộc:** `copy_chunk_references.py` phải chạy **sau**
> `seed_hr_from_legal.py`. ETL chunk xoá rồi insert lại nên **sinh UUID mới mỗi lần**;
> `chunk_references` FK theo `document_chunks.id` với `ON DELETE CASCADE` nên sẽ bị
> dọn sạch. Chạy lại `copy_chunk_references.py` sau là xong — nó idempotent.

> **Cập nhật 2026-10-06:** bước `verify_db.py` trong list cũ đã bị gỡ khỏi repo
> cùng bộ đo retrieval. Thay bằng các câu SQL đếm ở mục 4 của `handoff/README.md`.
> `pytest` vẫn là cổng chặn chính.

Lưu ý duy nhất hay vấp: bước step3 phải in `Tokenizer fallback used: False`.
Nếu `True` là thiếu `mistral-common` → `pip install -r requirements.txt`, chạy lại.

## 3. Số đúng để đối chiếu

**Không hardcode số ở đây.** Chạy
`.\.venv\Scripts\python.exe scripts\corpus_expectations.py` để in số đúng
tính từ `data/chunk/chunks_*.json` — cùng nguồn mà `embed_legal.py` dùng để
đối chiếu. Lệch số nào thì dừng, đừng seed tiếp.

Hiện tại: `legal_documents` 4 · `legal_chunks` 1377
(381+377+531+88) · refs 599 (BOUNDARY 3, UNRESOLVED 0) ·
embeddings 1377 (0 NULL) · `policies`/`documents` 4 ·
`document_chunks` 1377.

## 4. Thêm văn bản mới

1. Thả file vào `data/markdown/` (Điều đánh số tuần tự theo thứ tự đọc).
2. Thêm entry vào 3 chỗ: `DOC_ID_MAP` (`hierarchy_parser.py`),
   `DOCUMENTS` (`seed_legal.py`), `LEGAL_DOCS` (`seed_hr_from_legal.py`).
   *Không* sửa `CHUNK_FILES`/`TREE_FILES`/`EXPECTED_*`: các danh sách đó đã
   tự dẫn từ `data/chunk/chunks_*.json` qua `scripts/corpus_expectations.py`,
   nên thêm văn bản không làm hỏng số kỳ vọng nữa.
3. Đổi `chunk_id` (đánh số lại Điều) thì DELETE dòng cũ trước khi seed:
   `DELETE FROM legal_chunk_embeddings WHERE chunk_id LIKE '<PREFIX>%';
    DELETE FROM legal_chunks WHERE document_id='<id mới>';`
   (seed chỉ upsert, không xóa dòng cũ).
4. Chạy mục 2, review `git diff data/chunk/`.
5. Refresh dump + sha256, sửa số trong `handoff/README.md`, ghi 1 mục vào
   `data/chunk/CHANGELOG.md`.
