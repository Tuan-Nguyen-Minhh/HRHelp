# PLAN B6 + B7: Embedding (`legal_chunks`) → Hybrid Search (pgvector + BM25) — REV.1

## 0. Mục tiêu & nguyên tắc

- B6 biến 1289 chunk text thành 1289 vector `mistral-embed` 1024-dim, lưu cùng
  Postgres (`p-029-db-1`) làm source of truth cho vector. B7 dựng hybrid search
  (vector + BM25 tiếng Việt mức DB-native) và bộ eval cố định để chặn hồi quy.
- Một model duy nhất cho cả DB (DECISION 2026-09-26, đã chốt với tech lead):
  `mistral-embed`. Không OpenAI, không Qdrant — pgvector trong cùng Postgres
  (ext `vector` đã có, `vector_store.py` đã dùng `PGVector`).
- Idempotent + resume: mất mạng giữa chừng chạy lại không tốn quota oan, không
  trùng dòng. Rule đổi thì rác cũ bị phát hiện bằng hash, không âm thầm thiu.
- Không sửa text chunk, không sửa B4/B5 (verify B4/B5 phải xanh lại sau B6/B7).

## 1. Đầu vào (đóng băng)

- `legal_documents` (3), `legal_chunks` (1289), `legal_chunk_references` (565)
  ở migration head `0002_unify_mistral_embed`. Số liệu đo thật, không ước đoán:
  tổng **680 518 tokens** (Mistral tokenizer, từ `metadata.token_count`),
  trung bình **528**, max **1132**, chỉ **3 chunk > 1000 tokens**.
- `data/chunk/*.json` + `source_manifest.json` (6 file, đã track trong git).
- `.env`: `EMBEDDING_MODEL=mistral-embed`, `VECTOR_COLLECTION=regulations`.
- **Điều kiện tiên quyết, chưa có:** `MISTRAL_API_KEY` không tồn tại trong `.env`
  (đã kiểm bằng grep). B6 không chạy được cho tới khi thêm key. Quota team đã
  biết: **20M TPM / 1 RPS**.

## 2. B6 — việc phải làm

1. Model + migration `0003_legal_embeddings` (tạo bảng mới, không sửa bảng cũ):
   - `legal_chunk_embeddings`: `chunk_id` TEXT PK → FK `legal_chunks.chunk_id`
     `ON DELETE CASCADE`; `content_sha256 CHAR(64)` NOT NULL =
     sha256 của `legal_chunks.text` đúng tại thời điểm embed;
     `model` TEXT (`mistral-embed`), `dimensions` INT (`1024`);
     `embedding VECTOR(1024)` NOT NULL; `created_at/updated_at`.
   - **Vì sao bảng riêng, không nhét cột vào `legal_chunks`:** B5 là
     truncate-and-reseed (`seed_legal.py:399`); vector là tài sản đắt (quota)
     nên vòng đời phải tách khỏi vòng đời seed. Nhét chung thì mỗi lần reseed
     B5 là mất trắng vector. Cùng lý do không tái dùng cột `Vector(1536)` của
     `document_chunks`/`disciplinary_decisions` (đã về 1024 ở migration `0002`,
     nhưng hai cột đó thuộc HR Help — B6 không đụng).
   - **Vì sao `content_sha256` bắt buộc:** không có nó, ai sửa `text` (rerun
     step3, sửa tay) thì vector cũ vẫn nằm trong DB và search vẫn trả về —
     sai mà không tín hiệu nào báo. Có hash thì stale phát hiện được bằng 1 câu
     SQL (xem V2).
2. `scripts/embed_legal.py`:
   - Đọc 1289 chunk theo `chunk_id` tăng dần. Text embed = `header_context +
     "\n" + text` (giữ ngữ cảnh Điều/Chương như B7 sẽ query; chốt, không đổi sau).
   - Batch **32 texts/request**, throttle **≤ 1 RPS** (sleep bù theo timestamp
     thực, log mọi timestamp gọi API ra file để V7 audit được).
   - Resume an toàn: trước mỗi batch, bỏ qua chunk đã có dòng embedding **và**
     `content_sha256` khớp `text` hiện tại (đếm số skip ra log). Crash thì chạy
     lại, chỉ tốn quota cho phần còn thiếu.
   - Ghi checkpoint tiến trình ra `data/chunk/embed_progress.json` sau mỗi batch
     (giữ file này trong gitignore — trạng thái tạm, không phải deliverable).
   - Ước tính trần: 680 518 tokens ≈ **0,7M, ~3,4% quota TPM**; 1289/32 ≈ 41
     request ≈ **dưới 1 phút** gọi API ở 1 RPS (không batch sẽ ~22 phút — vì vậy
     batch là bắt buộc, không phải tối ưu tùy thích).
   - 3 chunk > 1000 tokens: vẫn embed trực tiếp (giới hạn model là 8k, còn xa),
     giữ flag `POINT_BODY_OVER_LIMIT` trong `meta` để audit.
3. Không dùng `PGVector` của langchain cho bảng này (bảng đó tự quản schema,
   không có `content_sha256`, không audit được). `src/services/vector_store.py`
   giữ nguyên cho agent runtime; B7 đọc vector từ `legal_chunk_embeddings`.

## 3. B7 — việc phải làm

4. Index (trong migration `0003`, chung với tạo bảng — 1289 dòng nên
   `CREATE INDEX` thường là đủ, không cần `CONCURRENTLY`):
   - HNSW cosine: `CREATE INDEX ix_legal_embeddings_hnsw ON
     legal_chunk_embeddings USING hnsw (embedding vector_cosine_ops)
     WITH (m = 16, ef_construction = 64)` (cùng tham số với index HR để một
     chuẩn vận hành).
   - BM25 DB-native: thêm cột generated `search_tsv TSVECTOR GENERATED ALWAYS
     AS (to_tsvector('simple', coalesce(header_context,'') || ' ' ||
     coalesce(text,''))) STORED` + GIN index. Ghi rõ giới hạn: Postgres không có
     stemmer tiếng Việt nên config là `simple` (tách từ + match chính xác, không
     chia từ ghép) — đủ cho thuật ngữ luật (số Điều, tên chế tài), không quảng
     cáo quá khả năng. Không kéo thêm service (Elasticsearch/Typesense) cho
     1289 dòng.
5. `src/services/hybrid_search.py` (service mới, agent sẽ gọi ở milestone sau):
   - Vector top-20 (cosine) + BM25 top-20 (`ts_rank_cd`) → hợp nhất bằng
     **RRF k=60** (chốt công thức, không để code tự chọn trọng số).
   - Tham số duy nhất lộ ra ngoài: `top_k` (mặc định 5). Mọi hằng số khác
     (k RRF, ef_search runtime) là hằng số có tên trong file, đổi phải qua
     review vì làm đổi kết quả V4–V6.
   - Filter theo `document_id` / `article_number` / `chunk_level` đẩy xuống SQL
     (dùng cột riêng của B4, không lọc trong Python sau khi lấy top-k).
6. Golden eval set `eval/legal_golden.json` (tạo mới, track trong git):
   - 10 query tiếng Việt phủ 3 văn bản + cả 3 cấp chunk, mỗi query kèm
     `expected_chunk_ids` (1–3 chunk) và `must_contain_article` (số Điều).
   - Đáp án ghim **sau** lần chạy đầu + review tay (giống V5-manual của B4/B5):
     chạy eval, người đọc từng kết quả, đúng mới ghim. Từ đó về sau đáp án là
     luật, đổi đáp án phải ghi lý do vào CHANGELOG.
   - Query mẫu đã định sẵn từ dữ liệu thật (không bịa trước khi có vector):
     tuổi nghỉ hưu → `BLLD:CXII:M00:A169:C02/C03`; mức phạt BHXH →
     `ND283_2026:CIII:M00:A044:C01` và các điểm; kỷ luật lao động →
     BLLD Đ122/Đ118; thời giờ làm việc → BLLD Đ107/Đ113; hợp đồng lao động →
     BLLD Đ21/Đ35; phạm vi NĐ145 → `ND145_2020:CI:M00:A001`.
7. `scripts/eval_retrieval.py`: chạy 10 query qua cả 3 đường (vector-only,
   BM25-only, hybrid), tính **Hit@1 / Hit@5 / MRR**, in bảng so sánh + ghi
   `eval/results/` (ghi đè có version theo ngày, giữ lịch sử như `verify_db_*.log`).
   Ngưỡng nhận nghiệm lần đầu: **Hit@5 ≥ 0,8 và MRR ≥ 0,6 trên hybrid, và hybrid
   không thua đường đơn nào quá 0,1 ở cả hai chỉ số**. Ngưỡng này là sàn chống
   hồi quy, không phải mục tiêu chất lượng cuối — thắt dần ở milestone agent.
8. Không làm bảng log retrieval persistent trong B7. Bảng `agent_runs` /
   `agent_retrievals` của HR dùng `chunk_id` UUID nên không FK được tới
   `legal_chunks` (PK text) — nhét vào sẽ phải bỏ FK, mất tính toàn vẹn. Log
   runtime của RAG legal đi cùng milestone agent, không phải B7.

## 4. Vòng lặp VERIFY (sau MỖI lần sửa, chưa đạt hết quay lại từ B6.1)

`scripts/verify_embeddings.py` (mới) chỉ tự động V1–V8 và in PASS/FAIL. Review tay
là bước ký riêng ngoài loop (V-manual). Dừng auto-loop khi tất cả mục auto đạt
cùng 1 lần chạy; nhận nghiệm cuối khi có thêm sign-off V-manual.
Phạm vi quay lại khi FAIL: lỗi thuộc B7 (rank, RRF, BM25, eval) thì **chỉ chạy lại
từ B7** (không đụng model/migration B6, không re-embed); mọi lỗi còn lại quay lại
từ B6.1. Ghi rõ phạm vi vào changelog. Sau B6/B7 phải chạy lại `verify_db.py`
(B4/B5) — đỏ chỗ nào là FAIL toàn bộ.

- [V1] Migration + schema: `alembic current` == head (`0003`); bảng
  `legal_chunk_embeddings` tồn tại; `embedding` là `VECTOR(1024)` thật (đọc
  `format_type`, không tin model); HNSW + GIN tồn tại; cột HR vẫn `VECTOR(1024)`.
- [V2] Đủ + đúng + tươi: đúng **1289 dòng** (không ±); 0 `embedding` NULL;
  `dimensions = 1024` hết; `vector_dims(embedding) = 1024` hết; **100%**
  `content_sha256` khớp sha256 của `legal_chunks.text` hiện tại —
  câu này bắt stale vector, không có là FAIL.
- [V3] Idempotent + số học quota: chạy `embed_legal.py` lần 2, số skip phải
  **= 1289** (0 request API mới — kiểm bằng log timestamp gọi API, không tin
  lời code); md5 toàn bộ 1289 vector trước/sau giống nhau; đổi 1 `text` rồi
  chạy lại thì đúng 1 dòng re-embed và sha mới khớp.
- [V4] Vector search golden (assert đáp án cứng trong script): mỗi query trong
  `eval/legal_golden.json`, `expected_chunk_ids` phải nằm trong top-5 vector-only.
  Thêm assertKC chống mục ruỗng: norm hữu hạn hết (không NaN/Inf), và embed lại
  5 chunk mẫu cho cosine **≥ 0,999** với vector đã lưu (bắt model/key bị đổi lén).
- [V5] BM25 + hybrid: `must_contain_article` của mỗi query phải xuất hiện trong
  top-5 của **cả ba đường** (vector/BM25/hybrid) — BM25 yếu tiếng Việt nên chỉ
  đòi mức Điều, không đòi đúng chunk. RRF với `k=60` đúng công thức (test đơn vị
  riêng với input giả, không dùng DB).
- [V6] Metrics sàn: trên 10 query, hybrid đạt **Hit@5 ≥ 0,8 và MRR ≥ 0,6**,
  và không thua đường đơn nào quá **0,1** ở cả hai chỉ số. Dưới sàn là FAIL,
  không "giải trình".
- [V7] Quota + resume: tổng tokens đã gọi ≤ **1M** (trần 0,7M + dự phòng);
  khoảng cách giữa 2 request liên tiếp **≥ 1,0s** (đọc từ log timestamp);
  kill tiến trình giữa chừng rồi chạy lại thì đủ 1289 dòng không lỗi, không trùng.
- [V8] Source untouched + không hồi quy: sha256 6 file JSON khớp
  `source_manifest.json`; `verify_db.py` (B4/B5) vẫn **70/70**; `mutation_test.py`
  vẫn **18/18**.
- [V-manual] (ngoài auto-loop, sign-off riêng): đọc tay top-5 hybrid của cả 10
  query, checklist ghi vào `eval/verify_retrieval_manual.md` (người review ký +
  ngày). Lần đầu còn là lúc **ghim đáp án** cho `legal_golden.json`.

## 5. Output cuối

1. Migration `alembic/versions/0003_*.py` + DB đã migrate (head `0003`).
2. `scripts/embed_legal.py`, `scripts/verify_embeddings.py`,
   `scripts/eval_retrieval.py`, `src/services/hybrid_search.py`.
3. `eval/legal_golden.json` + `eval/results/*` + `eval/verify_retrieval_manual.md`
   (sign-off tay, **chưa ký thì chưa nghiệm**).
4. `data/chunk/CHANGELOG_B6B7.md` + log mọi lần chạy (giữ cả FAIL, đánh số).
5. Dump milestone mới `handoff/b6_*` (dump B4/B5 cũ thiếu bảng vector → stale
   ngay khi B6 xong; đặt tên theo milestone, không ghi đè).

## 6. Không làm

- Không Qdrant/Elasticsearch; không sửa text/metadata chunk; không đụng bảng HR;
  không log retrieval persistent (đi cùng milestone agent); không đổi `chunk_id`
  scheme; không thắt ngưỡng V6 giữa chừng mà không ghi changelog.
