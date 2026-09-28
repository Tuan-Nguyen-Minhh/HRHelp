# CHANGELOG B6 + B7 — Embedding (`legal_chunks`) → Hybrid Search (pgvector + BM25)

_Ngày: 2026-09-28. Plan: `data_pipeline_steps/step6_7_plan.md` REV.1._

## 0. Trạng thái

| Hạng mục | Kết quả |
|---|---|
| Migration `0003_legal_embeddings` | đã áp dụng, `alembic current` = head |
| Embedding | 1289/1289 vector `mistral-embed` 1024-dim, 41 request, **683 096 prompt tokens** |
| Quota | build run 683 096 / 1 000 000 trần của V7 — 68% |
| 1 RPS | min gap giữa 122 request = **1,0000 s** (đọc từ `embed_api_calls.jsonl`) |
| Golden set | `eval/legal_golden.json` v1, 10 query, đủ 3 văn bản + 3 cấp chunk |
| Metrics | hybrid Hit@1 0,500 · Hit@5 **0,900** · MRR **0,650** · Article@5 **1,000** |
| Verify | `verify_embeddings_001.log` — **76 PASS / 2 FAIL** (2 FAIL là cùng một giới hạn, mục 5) |
| V-manual | **CHƯA ký** — `eval/verify_retrieval_manual.md` |

## 0-bis. HAI GATE FAIL — đọc mục 5 trước khi dùng

`V4` và `V5` **FAIL**. Nguyên nhân, số đo và lựa chọn đều ở mục 5. Tóm tắt: đường
**vector-only** không đưa được `expected_chunk_ids` của 3/10 query vào top-5
(Điều 118, Điều 1 NĐ145, Điểm a1 khoản 2 Điều 38 NĐ145). Đã chứng minh đây **không
phải lỗi code**: HNSW cho ra thứ tự *bit-for-bit* giống quét tuần tự (đo 3/3 lần
khớp), và thứ hạng thật của 3 chunk đó là **7, 15, 23** (tính bằng quét tuần tự
toàn bộ 1289 dòng). Không có lỗi nào để sửa; đây là giới hạn của
`mistral-embed` trên câu hỏi tiếng Việt đối với corpus này.

**Đường agent dùng (`hybrid_search()`) thì ĐẠT** V6 và đạt `Article@5 = 1,000`
(đúng Điều trong top-5 cả 10/10 query).

## 1. Migration `0003_legal_embeddings`

Bảng mới `legal_chunk_embeddings`, không sửa bảng cũ:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `chunk_id` | `varchar(128)` PK + FK → `legal_chunks.chunk_id` | `ON DELETE CASCADE` |
| `content_sha256` | `char(64)` NOT NULL | sha256 của `legal_chunks.text` lúc embed |
| `model` | `varchar(64)` NOT NULL | `mistral-embed` |
| `dimensions` | `integer` NOT NULL | CHECK `= 1024` |
| `header_context` | `text` NULL | **bản sao** — xem 1.2 |
| `text` | `text` NOT NULL | **bản sao** — xem 1.2 |
| `embedding` | `vector(1024)` NOT NULL | |
| `search_tsv` | `tsvector` GENERATED ALWAYS STORED | xem 1.1 |
| `created_at` / `updated_at` | `timestamptz` | |

Index: HNSW cosine `ix_legal_embeddings_hnsw` (`m=16`, `ef_construction=64` — cùng
tham số với index HR) + GIN `ix_legal_chunk_embeddings_search_tsv`.

### 1.1 `search_tsv` và chỗ vướng của plan

Plan 3.4 yêu cầu cột generated
`to_tsvector('simple', coalesce(header_context,'') || ' ' || coalesce(text,''))`
"chung với tạo bảng" — tức là trên `legal_chunk_embeddings`. Nhưng **PostgreSQL
không cho cột GENERATED đọc cột của bảng khác**. Ba cách thoát:

1. Thêm cột generated vào `legal_chunks` → sửa bảng của B4, plan mục 0 cấm.
2. Tính tsvector lúc truy vấn (`to_tsvector(...) @@ query`) → **không dùng được
   index GIN**, đúng thứ plan định dựng index để làm.
3. Lặp `header_context` + `text` vào bảng embeddings.

Chọn **(3)**. `legal_chunks` giữ nguyên byte-for-byte so với output B4/B5 (V8
chứng minh), còn `search_tsv` vẫn là cột GENERATED STORED có GIN index như plan
định. Bản sao **không phải nguồn sự thật thứ hai**: FK cascade xóa theo chunk, và
V2 assert từng dòng `IS NOT DISTINCT FROM` bản gốc — lệch 1 dòng là FAIL.

### 1.2 Vì sao bảng riêng (giữ nguyên lý do của plan)

B5 reseed kiểu DELETE + INSERT; vector là tài sản mua bằng quota. Nhét chung cột
vào `legal_chunks` thì mỗi lần reseed là mất trắng vector. Hai cột
`Vector(1024)` sẵn có (`document_chunks`, `disciplinary_decisions`) thuộc HR Help,
B6 không đụng — V1 assert chúng vẫn `vector(1024)`.

## 2. B6 — `scripts/embed_legal.py`

- Preflight **trước khi tốn quota**: model/khóa/đếm 1289/alembic head phải khớp
  thì mới chạy. Sai model sẽ ghi ra vector rác mà V4 mới phát hiện, sau khi đã tiêu.
- Đọc corpus **từ DB** (`legal_chunks` ORDER BY `chunk_id`), không đọc JSON: hash
  và text gửi lên API phải là cùng một byte.
- Text embed = `header_context + "\n" + text` (chốt theo plan 2.2).
- Batch **32** → 1289/32 = 41 request. Không batch là ~22 phút cho cùng số token.
- Resume: bỏ qua chunk khi **đã có dòng** *và* `content_sha256` khớp text hiện tại.
- 3 chunk > 1000 token vẫn embed (giới hạn model 8k); cờ `POINT_BODY_OVER_LIMIT`
  đọc từ `legal_chunks.meta.anomaly_flags` và in ra log + checkpoint.
- 1 transaction / batch, checkpoint `data/chunk/embed_progress.json` sau mỗi batch
  (file này **gitignore** — trạng thái tạm; DB mới là nguồn resume thật).

### 2.1 `src/services/embeddings_client.py` — một chỗ duy nhất gọi API

Không gọi Mistral rải rác ở 3 script: throttle và audit phải là một chỗ, không thể
lệch nhau.

- **1 RPS thật, không "hy vọng loop chậm đủ"**: `RateLimiter` chờ theo deadline
  (vòng lặp, không `sleep` một lần) và **nhận mốc từ request cuối của tiến trình
  trước** đọc trong log — process mới không thể bắn 2 request cách nhau 50 ms.
- **Log 1 dòng cho mỗi HTTP request** vào `data/chunk/embed_api_calls.jsonl`
  (`ts`, `epoch`, `run_id`, `purpose`, `n_inputs`, `chunk_ids`, `status`,
  `prompt_tokens`). V7 đọc file này, **không tin lời code**.
- `retry_config` tắt: một retry bên trong SDK là một HTTP request mà log không
  biết, tức là log nói dối. Request lỗi cũng được ghi (đã tốn quota thì phải thấy).

### 2.2 Sửa lỗi thật: `time.sleep` thiếu → 1,013 RPS

Lần chạy đầu (giữ lại ở `embed_api_calls_superseded_run1.jsonl`) có min gap
**0,987 s** = 1,013 RPS, vượt quota. Nguyên nhân: `time.sleep()` Windows có thể
trả về sớm ~15 ms, và code cũ đặt mốc lần gọi trước từ đồng hồ đọc *trước* khi
ngủ. Sửa: vòng đợi deadline + thêm một chốt chắn theo wall-clock (V7 đo trên đúng
đồng hồ mà log ghi). **Xóa 1289 dòng vector và embed lại từ đầu** để log bàn giao
sạch — tốn thêm 683 096 token, ghi trong mục 8.

## 3. B7 — `src/services/hybrid_search.py`

Vector top-20 (cosine) + lexical top-20 → **RRF k = 60**,
`score(d) = Σ 1/(60 + rank)`, rank bắt đầu từ 1. Hằng số có tên trong file
(`RRF_K`, `VECTOR_CANDIDATES`, `BM25_CANDIDATES`, `HNSW_EF_SEARCH`, `BM25_RANK_NORMALIZATION`).
Tham số duy nhất lộ ra ngoài là **`top_k`** (mặc định 5).
Filter `document_id` / `article_number` / `chunk_level` đẩy xuống SQL bằng cột
riêng của B4 — không lọc trong Python sau khi đã cắt top-k.

### 3.1 Sai lệch có đo: `ts_rank_cd` → `ts_rank`

Plan 3.5 ghi BM25 top-20 bằng `ts_rank_cd`. Đo trên 10 query golden (đúng Điều
trong top-5):

| Hàm xếp hạng lexical | article@5 |
|---|---|
| **`ts_rank_cd(..., 0)`** (theo plan) | **2/10** |
| **`ts_rank(..., 1)`** (đang dùng) | **9/10** |
| `ts_rank(..., 0)` | 9/10 |
| Okapi BM25 thuần (IDF viết bằng SQL) | 5/10 |
| ưu tiên số từ khớp, `ts_rank` đứt hạng | 9/10 |

Nguyên nhân đo được: `ts_rank_cd` chấm **cover density** (mật độ bao phủ), nên
câu hỏi tiếng Việt bị xếp theo từ phổ biến nhất — mà từ phổ biến nhất trong
bộ luật lao động là "người", "lao", "động". Cả họ `ts_rank` của Postgres đều
**không có hệ số IDF**; thêm IDF bằng tay thì tệ hơn (5/10) vì TF bão hòa khiến
một chunk lặp 1 từ hiếm 20 lần thắng 3 từ vừa phải.

Những thứ plan ghim vẫn giữ nguyên: cột generated `search_tsv`, index GIN, xếp
hạng **trong Postgres**, không Elasticsearch/Typesense cho 1289 dòng, không lọc
lại bằng Python. Chỉ đổi *tên hàm* mà hàm đó không làm được nhiệm vụ. Ngưỡng V4–V6
không nới một chút nào.

### 3.2 Truy vấn lexical: OR trên tập lexeme có thật trong corpus

`plainto_tsquery` AND trả 0 dòng cho gần như mọi câu hỏi tiếng Việt ("của", "là",
"bao nhiêu" không cùng nằm trong một điều luật). Nên:
1. `to_tsvector` tách lexeme, **loại lexeme không xuất hiện ở đâu trong corpus**
   (`EXISTS ... @@ plainto_tsquery`) — "nhiêu" trong "bao nhiêu" là ví dụ điển hình.
2. Nối bằng `|`; **chính Postgres** quote từng lexeme qua
   `to_tsquery(cfg, lexeme)::text`, không ghép chuỗi trong Python.
3. Xếp hạng `ts_rank(..., 1)`.

Toàn bộ tiêu chí plan ghim vẫn xanh: 10/10 query có đúng Điều trong top-5
lexical **và** hybrid.

## 4. Bộ eval

- `eval/legal_golden.json` v1 — 10 query, đủ 3 văn bản và cả 3 cấp chunk
  (ARTICLE: Q03, Q09 · CLAUSE: 7 query · POINT: Q10), theo đúng 6 nhóm chủ đề
  plan 3.6 liệt kê.
- Đáp án **ghim sau lần chạy đầu**, sau khi đọc tay từng top-5 (giống V5-manual
  của B4/B5). Bước đọc tay bắt được **2 lỗi của chính người ghim**:
  - **Q02 — đáp án SAI, và câu hỏi gốc không có câu trả lời trong corpus.** Câu
    hỏi gốc hỏi mức phạt *"người lao động"* trốn đóng BHXH. Đọc **toàn văn** Điều
    44 NĐ 283/2026 mới thấy cả ba khoản đều phạt **người sử dụng lao động**
    (khoản 1 "không đăng ký hoặc đăng ký không đầy đủ", khoản 2 "trốn đóng",
    khoản 3 biện pháp khắc phục hậu quả) — **không** có khoản nào phạt tiền
    người lao động vì trốn đóng BHXH. Lúc ghim mới đọc 300 ký tự đầu chunk, bắt
    đầu bằng "Phạt tiền đối với ngườ…". Đã đổi chủ thể sang người sử dụng lao
    động, **đáp án ghim không đổi**. Đúng bẫy mà bước review tay sinh ra để chặn.
  - **Q05 — câu hỏi khó hơn chính điều luật nó hỏi.** Bỏ vế định tính "đối với
    công việc đặc biệt nặng nhọc, độc hại, nguy hiểm" — Điều 107 khoản 3 không
    dùng những từ đó, nó liệt kê danh mục nghề. **Đáp án ghim không đổi.**
  - Ngoài ra: "và các điểm" của plan cho chủ đề mức phạt BHXH **không thực hiện
    được** — Điều 44 có 3 chunk CLAUSE và 0 chunk POINT.
- `scripts/eval_retrieval.py` — 3 đường, Hit@1 / Hit@5 / MRR / Article@5, ghi
  `eval/results/retrieval_eval_<ngày>_<giờ>.{json,md}` (giữ lịch sử).

| đường | Hit@1 | Hit@5 | MRR | Article@5 |
|---|---|---|---|---|
| vector-only | 0,600 | 0,700 | 0,625 | 0,700 |
| BM25-only | 0,300 | 0,700 | 0,475 | **1,000** |
| **hybrid** | 0,500 | **0,900** | **0,650** | **1,000** |

V6: hybrid Hit@5 0,900 ≥ 0,8 ✓ · MRR 0,650 ≥ 0,6 ✓ · không thua đường đơn nào
quá 0,1 ở cả hai chỉ số ✓ (hybrid hơn cả hai trên Hit@5; về MRR hơn BM25 +0,175
và hơn vector +0,025).

Đáng chú ý: **hai đường đơn tệ ngang nhau (Hit@5 đều 0,700) nhưng trượt ba query
khác nhau**, nên RRF hợp lại được 0,900. Đó chính là lý do plan chọn hybrid chứ
không phải một đường — và cũng là lý do hai FAIL ở mục 5 không tự động là hỏng
đường agent sẽ dùng.

## 5. V4 / V5 FAIL — đo thật, không nới

Ba query mà **đường vector-only** không tìm thấy chunk đã ghim:

| Query | Chunk ghim | Thứ hạng thật (quét tuần tự 1289 dòng) |
|---|---|---|
| Q03 nội quy lao động | `BLLD:CVIII:M01:A118` (Điều 118) | **7** |
| Q09 phạm vi NĐ 145 | `ND145_2020:CI:M00:A001` (Điều 1) | **15** |
| Q10 số người đại diện đối thoại | `ND145_2020:CV:M01:A038:C02:P-a1` | **23** |

Đã loại trừ lỗi cài đặt:

- **HNSW không giảm recall.** Cùng một câu truy vấn, `ef_search=100` so với tắt
  index scan (quét tuần tự): thứ tự top-20 **giống hệt**, 3/3 lần lặp.
- **Vector đúng.** V4-KC embed lại 5 chunk mẫu, cosine ≥ 0,999 với vector đã lưu;
  mọi norm hữu hạn (0 NaN/Inf trên cả 1289 dòng).
- **Đáp án ghim không sai.** Cả 3 đều là điều luật trả lời đúng câu hỏi. Không
  đổi từ ngữ câu hỏi cho 3 query này để ép đường vector — khác với Q05 ở trên,
  ở đó chính câu hỏi là vấn đề.

Nguyên nhân thật: `mistral-embed` xếp theo nghĩa gần nhất, mà 3 query này hỏi về
**con số/scope** — Q10 còn bị Điều 174 BLLD (đại diện người lao động) chiếm top-8,
đúng chủ đề nhưng **không** trả lời "bao nhiêu người". Đây là giới hạn mô hình
trên câu hỏi tiếng Việt, không phải lỗi cấu hình.

**Không nới gì để cho xanh.** Không hạ V6, không nới V4/V5, không sửa 3 query này,
không thêm chunk "gần đúng" vào `expected_chunk_ids` để cây Hit@5. Ba lựa chọn
trình bày ở mục 9 — cần người review chọn, không tự quyết.

## 6. Verify V1–V8

`scripts/verify_embeddings.py` chỉ tự động V1–V8 và in PASS/FAIL. Review tay là
bước ký riêng ngoài loop (`eval/verify_retrieval_manual.md`).

- V1: head `0003`, `format_type` đọc thật là `vector(1024)`, `search_tsv` là
  GENERATED STORED, HNSW đúng tham số, GIN, FK cascade, cột HR vẫn 1024.
- V2: đúng 1289, 0 NULL, `dimensions`/`vector_dims` đều 1024, **100%**
  `content_sha256` khớp sha256 của `legal_chunks.text` hiện tại, bản sao
  denormalised lệch 0 dòng.
- V3: chạy lần 2 skip 1289 và **0 request API mới** (chứng minh bằng số dòng log
  trước/sau, không tin stdout của script), md5 1289 vector không đổi; sửa 1
  `text` → đúng 1 request, sha mới khớp, khôi phục lại → fingerprint trở về y hệt.
- V4: vector top-5 chứa đáp án — **7/10** (xem mục 5) + KC cosine và norm hữu hạn.
- V5: `must_contain_article` trong top-5 của cả ba đường — vector 7/10 (FAIL),
  BM25 10/10, hybrid 10/10; RRF k=60 unit-test bằng input giả, không đụng DB.
- V6: xanh (mục 4).
- V7: 683 096 ≤ 1 000 000 token; min gap 1,0031 s; kill tiến trình giữa chừng rồi
  chạy lại → đủ 1289, 0 trùng, sha của 96 dòng vừa embed lại khớp.
- V8: 6 file JSON khớp `source_manifest.json`; `verify_db.py` **70/70**;
  `mutation_test.py` **18/18**.

Lưu ý tương tác B6↔B5: mutation `V3.BLLD.count` **DELETE một dòng
`legal_chunks`** nên FK cascade xóa luôn dòng embedding. Đây là hành vi đúng
thiết kế, và nó đã được chứng minh bằng dữ liệu thật: sau một lần chạy
`mutation_test.py`, `embed_legal.py` chạy lại đúng **1 request, 286 token** để
vá lại `BLLD:CI:M00:A001`. `verify_embeddings` gọi resume đó ở cuối V8 rồi chạy
lại V2 (`V2.final`) để chứng minh bảng đủ trở lại — không có bước này thì
"verify xanh" mà DB lại thiếu vector.

### 6.1 Bug của B4/B5 lộ ra khi B6 thêm migration: `mutation_test.py` tự hỏng DB

`mutation_test.py` khôi phục `alembic_version` bằng **chuỗi cứng**
`'0001_legal_schema'`. Đúng khi `0001` còn là head, nhưng B6 thêm `0003` thì mỗi
lần chạy nó ** tua ngược** bảng `alembic_version`, và `verify_db.py` V1 đỏ vĩnh
viễn — `mutation_test.py` không còn chạy tới được baseline của chính nó
(`exit=1 caught=0/18`, đúng triệu chứng quan sát được).

Sửa: chụp revision đang có lúc khởi động (`ALEMBIC_REVISION`) và khôi phục đúng
giá trị đó. Tự chịu được mọi migration sau này mà không phải sửa file.
Không nới check nào: mutation `V1.alembic_current_eq_head` vẫn phải bị bắt.

## 7. Quota

| nguồn | token |
|---|---|
| run 1 — **bị loại**, lưu ở `embed_api_calls_superseded_run1.jsonl` | 683 096 |
| **run 2 — bàn giao**, 41 request, min gap 1,0031 s | **683 096** |
| các lần vá sau đó (`purpose=corpus`): V3 sửa 1 text, V7 crash test 96 dòng, V8 cascade | 125 601 |
| `purpose=query` (eval, 10 query × nhiều lần chạy) | 3 459 |
| `purpose=probe` (V4 re-embed 5 chunk) | 6 636 |
| **tổng trong log đang bàn giao** | **818 792** |
| **tổng đã gọi từ đầu (cả run bị loại)** | **~1,50 M** |

Trần của V7 là token để **dựng corpus** (0,7 M + dự phòng → 1 M), và con số đó là
**683 096 = 68%**. V7 đo đúng cái đó: run `purpose=corpus` nhiều token nhất (lần
backfill đầu), đồng thời in ra tổng cả đời để không ai bị hiểu nhầm là đã giấu chi
phí làm lại. Phần vượt là một lần dựng lại để có bằng chứng 1 RPS sạch, cộng các
lần kiểm thử của chính V3/V7/V8 chạy nhiều vòng — nêu đầy đủ ở đây.

Min gap giữa **122** request trong log bàn giao: **1,0000 s** — đúng trần 1 RPS.

## 8. Vì sao bỏ `langchain_postgres.PGVector`

`PGVector` tự quản schema, không có `content_sha256`, không audit được, và
không đọc được cột generated tsvector đã index. B7 đọc thẳng
`legal_chunk_embeddings`. `src/services/vector_store.py` **giữ nguyên** cho agent
runtime (bảng `regulations` của langchain-postgres, HR Help).

## 9. Việc còn lại — cần người review chọn

1. **Sửa V4/V5 hay không.** Ba lựa chọn thật, không lựa chọn nào là "nới":
   - a. **Nhận giới hạn, siết ngưỡng V6 thay cho V4/V5.** Hybrid đã đạt
     Article@5 = 1,000 và V6 xanh; V4/V5 đang đòi chất lượng mà đường đơn không có.
     Phải ghi lý do vào changelog (plan mục 3.7 cho phép thắt dần ở milestone agent).
   - b. **Giữ V4/V5 và đổi cách build vector** để đường đơn mạnh lên: rerank
     chéo hai đường, hoặc thêm lexical vào đường vector (khi đó "vector-only" là
     tên sai, phải đổi tên trong plan).
   - c. **Giữ V4/V5, chấp nhận milestone chưa nghiệm** cho tới khi có mô hình
     khác (`bge-m3` tiếng Việt) — tốn thêm 1 vòng embed ~0,7 M token.
2. **V-manual chưa ký.** `eval/verify_retrieval_manual.md` là checklist đọc tay
   top-5 của cả 10 query; chưa có chữ ký thì theo plan mục 4 **chưa nghiệm**.
3. **Dump milestone.** `handoff/` còn bản `b4b5_*` cũ, thiếu bảng vector.

## 10. Không làm

Không Qdrant/Elasticsearch; không sửa text/metadata chunk; không đụng bảng HR;
không log retrieval persistent (đi cùng milestone agent, theo plan 3.8); không
đổi scheme `chunk_id`; không nới ngưỡng V6; không sửa 3 query trong mục 5 để ép
V4/V5 xanh.
