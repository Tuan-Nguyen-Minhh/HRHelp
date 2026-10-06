# Hỏi đáp: hai kho `legal_*` và `document_chunks`

- **Ngày kiểm chứng:** 29/09/2026
- **Cơ sở:** nhánh `main` @ `99a3b72` (đã merge `tuan_data_pipeline` qua PR #10), đọc thêm `origin/qminh/log-in-and-other`
- **Đo trực tiếp:** container `p-029-db-1`, database `build_phase_p029`, `.venv` của repo
- **Phạm vi:** trả lời các câu hỏi một dev khác trong dự án sẽ hỏi, ưu tiên bảng `legal_*` và `document_chunks`

> Tài liệu này **thay thế** phần 7 của `conversation-legal-va-document-chunks.md`. Số đo ở mục 7 của file đó đã cũ (xem câu 12).

---

## ⚠️ Đọc trước — trạng thái đã thay đổi (cập nhật 06/10/2026)

File này ghim theo commit `99a3b72` ngày 29/09/2026 và **giữ nguyên số đo tại ngày đó**
để làm bản ghi. Nhưng hiện tại đã khác:

| | Ngày 29/09 (file này) | Hiện tại 06/10 |
|---|---|---|
| `legal_documents` | 3 | **4** (thêm nội quy `NQLD-HRCORP-2026`) |
| `legal_chunks` | 1289 | **1377** (BLLD 381 / NĐ145 377 / NĐ283 531 / NQCT 88) |
| `legal_chunk_references` | 565 | **599** |
| `legal_chunk_embeddings` | 1289 | **1377** |
| `policies` / `policy_versions` / `documents` / `document_chunks` | **0** | **4 / 4 / 4 / 1377** |
| `alembic_version` | `0003_legal_embeddings` | `0010_conversation_memories` |

Hai việc đã xảy ra sau ngày ghim:

1. **ETL `scripts/seed_hr_from_legal.py` đã chạy** — `document_chunks` không còn
   rỗng. Đây là lý do câu 12 (mục 7) bên dưới không còn đúng: nó nói "không có lệnh
   `INSERT` vào `document_chunks`", nhưng hiện tại đã có 1377 dòng.
2. **Bộ đo retrieval đã bị gỡ** — `src/services/hybrid_search.py`,
   `scripts/{verify_db,verify_embeddings,eval_retrieval,mutation_test}.py` và
   `eval/results/retrieval_eval_*` không còn trong repo. Số liệu Hit@5/MRR ở mục 6
   và mục 8 là lịch sử, **không dùng làm bằng chứng** vì chúng đo một engine mà
   agent không gọi.

Đường retrieval thật của hồ sơ là `src/features/cite/model/pipeline.py`, đọc
`document_chunks`. Xem `ARCHITECTURE.md`.

---

## 0. Bảng tra nhanh — trạng thái thật ngày 29/09/2026

| Bảng | Số dòng | Ai ghi | Ai đọc |
|---|---|---|---|
| `policies` | **0** | — (chưa có code ghi) | cite, answer |
| `policy_versions` | **0** | — | cite |
| `documents` | **0** | — | cite |
| `document_chunks` | **0** | — | cite, `agent_retrievals`, `recommendation_citations` |
| `legal_documents` | **3** | `scripts/seed_legal.py` | `hybrid_search` (lọc), script |
| `legal_chunks` | **1289** | `scripts/seed_legal.py` | `hybrid_search`, `verify_*` |
| `legal_chunk_references` | **565** | `scripts/seed_legal.py` | **không ai trong runtime** |
| `legal_chunk_embeddings` | **1289** | `scripts/embed_legal.py` | `hybrid_search`, `verify_*` |
| `cases` / `messages` / `users` / `violation_types` | 0 / 0 / 0 / 0 | — | — |

`alembic_version` = **`0003_legal_embeddings`** (đã hơn `04e5c85e7957`).

Lệnh kiểm lại:

```bash
docker start p-029-db-1
docker exec p-029-db-1 psql -U postgres -d build_phase_p029 \
  -c "select version_num from alembic_version;" \
  -c "select 'policies' t,count(*) from policies union all
      select 'document_chunks',count(*) from document_chunks union all
      select 'legal_chunks',count(*) from legal_chunks union all
      select 'legal_chunk_embeddings',count(*) from legal_chunk_embeddings;"
```

---

## 1. Hai kho này có quan hệ gì với nhau không?

**Không.** Không khóa ngoại, không view, không trigger, không đồng bộ.

Chuỗi FK thật của nhóm hồ sơ (kiểm từ `\d document_chunks`):

```
policies.id
  └─ policy_versions.policy_id
       └─ documents.policy_version_id
            └─ document_chunks.document_id
                 ├─ agent_retrievals.chunk_id            (ON DELETE CASCADE)
                 └─ recommendation_citations.chunk_id    (ON DELETE SET NULL)
```

Chuỗi FK thật của kho legal:

```
legal_documents.document_id
  ├─ legal_chunks.document_id                    (ON DELETE CASCADE)
  │    └─ legal_chunk_embeddings.chunk_id        (ON DELETE CASCADE)
  └─ legal_chunk_references.source_chunk_id       (ON DELETE CASCADE)
       └─ legal_chunk_references.target_chunk_id  (ON DELETE SET NULL, nullable)
```

`legal_chunks.parent_chunk_id` là **TEXT không có FK** (1030/1030 giá trị đều treo — 0 resolve; đây là quyết định thiết kế từ step3, xem `handoff/README.md` mục 6).

Cột `document_chunks.content` tự chứa chữ. Cột `legal_chunks.text` cũng tự chứa chữ. **Hai kho là hai bản sao độc lập của cùng một điều luật.**

---

## 2. Cite của hồ sơ đọc bảng nào? Đọc theo điều kiện nào?

`src/features/cite/model/store.py`, hàm `_candidate_stmt()` — **một** câu SELECT duy nhất phục vụ cả 3 nhánh:

```sql
SELECT dc.id, dc.content, dc.article, dc.clause, dc.point,
       pv.id, p.policy_type, p.code, p.name
FROM document_chunks dc
JOIN documents     d  ON d.id  = dc.document_id
JOIN policy_versions pv ON pv.id = d.policy_version_id
JOIN policies      p  ON p.id  = pv.policy_id
WHERE pv.status = 'ACTIVE'
  AND pv.effective_from <= :incident_date
  AND (pv.effective_to IS NULL OR pv.effective_to >= :incident_date)   -- tính cả ngày cuối
  AND p.is_active IS TRUE
  AND d.ingest_status IN ('CHUNKED','EMBEDDED')
```

Đó là toàn bộ điều kiện. **Không có `legal_chunks` trong đó.**

Bốn nhánh:

| Nhánh | Hàm | Nguồn | Ghi chú |
|---|---|---|---|
| `similarity` | `fetch_by_similarity` | `document_chunks.embedding` cosine | **luôn rỗng — xem câu 8** |
| `bm25` | `fetch_in_force` (limit 200) + `bm25.bm25_rank` | Python Okapi BM25, k=1.5 b=0.75 | pool 200 dòng |
| `lexical` | `fetch_candidates` (limit 40) + `rank_passages` | `content ILIKE %term%` | |
| `page_index` | `fetch_article_index` (limit 80) | `content`/`section_title`/`metadata.article_title` | chỉ chạy khi 3 nhánh trên rỗng |

Sau đó: `rrf` (k=60, `RETRIEVAL_K=8`) → `rerank` (hiện là no-op, chỗ gắn cross-encoder) → `handoff`.

---

## 3. `hybrid_search` đọc bảng nào, ai gọi nó?

`src/services/hybrid_search.py`. SQL của cả hai cánh:

```sql
FROM legal_chunk_embeddings e JOIN legal_chunks c ON c.chunk_id = e.chunk_id
```

Vector arm: `<=>` cosine, HNSW `ix_legal_embeddings_hnsw`, `SET LOCAL hnsw.ef_search = 100`, top 20.
Lexical arm: `ts_rank(e.search_tsv, q, 1)` trên tsvector `GENERATED ALWAYS STORED` `to_tsvector('simple', header_context || ' ' || text)`, GIN, top 20.
Gộp: RRF k=60. `top_k` mặc định 5.

**Người gọi trong toàn repo (grep toàn bộ):**

| File | Mục đích |
|---|---|
| `scripts/eval_retrieval.py` | chạy bộ 10 câu golden, 3 cánh |
| `scripts/verify_embeddings.py` | gate V4–V8 |
| `scripts/embed_legal.py` (gián tiếp qua `embed_query`) | không; nó tự gọi client |

**Không file nào trong `src/` import `hybrid_search`.** `grep -r "hybrid_search" src/` chỉ ra chính file định nghĩa. Đây là cửa B8, chưa làm.

Chạy thử ngay (đã chạy hôm nay):

```bash
.venv\Scripts\python.exe -c "from src.services.hybrid_search import search; \
[h.print(h.citation, h.score) for h in search('Nhan vien nghi khong phep 5 ngay trong 30 ngay', top_k=5)]"
```

Kết quả thật (query tiếng Việt không dấu để tránh lỗi console Windows):

```
18/VBHN-VPQH Điều 112 [BLLD:CVII:M02:A112]  rrf=0.02711  vrank 18  brank 10
18/VBHN-VPQH Điều 113 [BLLD:CVII:M02:A113:C03] rrf=0.01639  vrank 1  brank None
18/VBHN-VPQH Điều 137 [BLLD:CX:M00:A137:C04] rrf=0.01639  vrank None brank 1
18/VBHN-VPQH Điều 83  [BLLD:CV:M03:A083]      rrf=0.01613  vrank 2   brank None
18/VBHN-VPQH Điều 125 [BLLD:CVIII:M01:A125]  rrf=0.01613  vrank None brank 2
```

Điều 125 (sa thải khi tự ý bỏ việc) **có mặt ở top-5** — nhưng cite của hồ sơ không đọc được nó.

---

## 4. Số liệu chuẩn của kho legal (đo lại 29/09/2026)

### 4.1 `legal_documents` — 3 dòng

| document_id | doc_code | type | form | status | article_count | chunk_count | `amended_by` |
|---|---|---|---|---|---|---|---|
| `18/VBHN-VPQH` | BLLD | BO_LUAT | VAN_BAN_HOP_NHAT | `PARTIALLY_AMENDED` | 220 | 381 | có JSONB |
| `145/2020/NĐ-CP` | ND145_2020 | NGHI_DINH | VAN_BAN_GOC | `ACTIVE` | 115 | 377 | SQL NULL |
| `283/2026/NĐ-CP` | ND283_2026 | NGHI_DINH | VAN_BAN_GOC | `ACTIVE` | 68 | 531 | SQL NULL |

Hai dòng NULL là **SQL NULL thật**, nhờ `JSONB(none_as_null=True)`; nếu không, `IS NULL` sẽ không khớp (chi tiết ở docstring `src/models/legal.py`).

`document_id` chứa `/` → phải URL-encode khi đặt vào path.

### 4.2 `legal_chunks` — 1289 dòng, phân bố theo cấp

| chunk_level | BLLD | ND145 | ND283 | tổng |
|---|---|---|---|---|
| `ARTICLE` | 186 | 61 | 12 | **259** |
| `CLAUSE` | 163 | 201 | 261 | **625** |
| `POINT` | 32 | 115 | 258 | **405** |
| tổng | 381 | 377 | 531 | **1289** |

Cột lọc riêng, đều có index: `article_number`, `clause_number`, `point_letter`, `chunk_level`.

**Điểm đáng chú ý cho dev:** Điều 125 BLLD chỉ có **một** chunk cấp `ARTICLE`:

```
BLLD:CVIII:M01:A125 | 18/VBHN-VPQH | article 125 | clause NULL | point NULL | ARTICLE
"Hình thức xử lý kỷ luật sa thải được người sử dụng lao động áp dụng trong trường hợp sau đây: 1. Người lao động có hành vi..."
```

Không có chunk `CLAUSE`/`POINT` cho Điều 125. Nếu sau này map `legal_chunks` → `document_chunks`, hãy nhớ chỗ này không tách được theo khoản.

### 4.3 `legal_chunk_references` — 565 cạnh

| `rule` | số dòng |
|---|---|
| `EXPLICIT_SELF` | 253 |
| `EXPLICIT` | 191 |
| `DEFAULT_SELF` | 72 |
| `SCOPED_CHAPEAU` | 25 |
| `LIST_EXPANSION` | 18 |
| `BOUNDARY_CHECK` | 3 |
| `QUOTED_EXTERNAL` | 3 |

- `target_chunk_id IS NULL`: **60** dòng → trích luật ngoài bộ 3 văn bản (Luật BHXH, Luật Công đoàn, `124/2025/QH15`…). **Không phải dữ liệu hỏng.**
- `needs_review = true`: **3** dòng, tất cả `needs_reason = 'BOUNDARY'`.
- **Không runtime nào đọc bảng này.** `hybrid_search` không join nó.

### 4.4 `legal_chunk_embeddings` — 1289 dòng

- `model = 'mistral-embed'`, `dimensions = 1024`, `vector_dims(embedding) = 1024`, 0 NULL.
- `content_sha256` khớp 100% với sha256 của `legal_chunks.text` hiện tại (V2 của verify).
- `header_context` / `text` là **bản sao** của `legal_chunks`, drift = 0 dòng.
- Index: `ix_legal_embeddings_hnsw` (HNSW cosine, m=16, ef_construction=64 — **không có** predicate `WHERE embedding IS NOT NULL`, khác `document_chunks` là có) + `ix_legal_chunk_embeddings_search_tsv` (GIN).

### 4.5 Chất lượng tìm kiếm (đo lại hôm nay)

`scripts/verify_embeddings.py` chạy lại: **76 PASS / 2 FAIL**.
`scripts/verify_db.py`: **70 PASS / 0 FAIL**.

| cánh | Hit@1 | Hit@5 | MRR | Article@5 |
|---|---|---|---|---|
| vector-only | 0,600 | 0,700 | 0,625 | 0,700 |
| bm25-only | 0,300 | 0,700 | 0,475 | **1,000** |
| **hybrid** | 0,500 | **0,900** | **0,650** | **1,000** |

2 FAIL là V4/V5 của cánh vector-only (Điều 118, Điều 1 NĐ145, Điểm a1 Điều 38 NĐ145 — thứ hạng thật 7/15/23). Đã chứng minh không phải bug HNSW, không phải vector sai; là giới hạn `mistral-embed` trên câu hỏi hỏi **con số/scope**. Nguyên nhân đầy đủ: `data/chunk/CHANGELOG_B6B7.md` mục 5.

---

## 5. Một luồng cite chạy hết thì ra gì, từng bước?

Ví dụ «Người A nghỉ không phép 5 ngày», `incident_date = 2026-03-01`.

**Bước 1 — `POST /api/v1/cases`**
`open_case()` → `build_case_graph(retrieve, opener)` → node `open` → `INSERT cases` (`OPEN`) + `conversations` (`ACTIVE`). Chưa động tới văn bản.

**Bước 2 — `POST /cases/{id}/messages`**
`handle_message()` → ghi `messages` (`USER`), `agent_runs` (`RUNNING`, model `hr-help-rules`) → graph `step=clarify` → `extract_node`.

Đo thật hôm nay:

```
detect_family("Người A nghỉ không phép 5 ngày")  -> UNAUTHORIZED_ABSENCE
required_specs                                   -> contract_type, absence_days,
                                                   notice_form, minutes_made,
                                                   explanation_requested
extract_facts(...)                               -> {'absence_days': '5 ngày'}
```

`"không phép"` khớp `_ABSENCE_MARKERS` nên family là `UNAUTHORIZED_ABSENCE`, không phải `GENERAL`. Cụm `"không"` trong `_NOTICE` không được hiểu thành `"không báo"` — `_notice()` chỉ nhận `"không báo"` / `"không xin"`. Còn 4 fact trống → `cases.status = NEED_INFO`, `case_facts` ghi `confirmed=false`, bot hỏi loại hợp đồng.

**Bước 3 — `POST /cases/{id}/facts/confirm` khi đủ 5 fact**
`_confirm()` → `_apply()` ghi `confirmed=true` → `_planned()` lại → `plan.locked = True` → `_cite()`.

Câu truy vấn (đo thật với `search_terms`):

```
terms    = ['luật', 'thải', 'nghỉ', 'phép', 'việc', 'người']
anchors  = ('sa thải', 'kỷ luật', 'nghỉ không phép', 'tự ý bỏ việc', 'đơn phương chấm dứt')
```

`_HINTS[ABSENCE] = "kỷ luật sa thải nghỉ không phép tự ý bỏ việc"` đứng đầu, rồi fact, rồi mô tả; tối đa 12 từ (`_LIMIT = 12`).

**Bước 4 — cite**
`search_policies()` ghi `tool_calls` (`search_policy`, `RUNNING`) với input `{query, incident_date, terms, retrievers:[similarity,bm25,lexical,page_index]}` → chạy retrieval graph.

**Kết quả thật hôm nay: cả 4 nhánh rỗng.** `policies` có 0 dòng nên `_candidate_stmt` không ra dòng nào; `page_index` cũng vậy. `rerank` trả `hits=[]` → `_after_rerank` sang `page_index` → `fetch_article_index` cũng rỗng → `retrieval="empty"`.

Đóng `CaseHandoff`:

```python
CaseHandoff(
    incident_date=date(2026,3,1),
    family="UNAUTHORIZED_ABSENCE",
    facts={5 fact đã confirmed},
    passages=[],                    # rỗng
    missing_internal_rule=True,     # vì passages rỗng
    retrieval="empty",
    ...
)
```

Tin `ASSISTANT` ghi vào `messages.metadata.kind = "handoff"`:
> "Không tìm thấy đoạn còn hiệu lực cho hồ sơ này. Chưa lập căn cứ trích dẫn. Message để trống phần văn bản cho agent đề xuất chế tài."

**`agent_retrievals` ghi 0 dòng** (không có chunk nào để ghi).

**Lưu ý quan trọng:** `cases.status` sau bước 3 **vẫn là `NEED_INFO`**, không phải `ANALYZED`. Chỉ `answers.publish()` mới set `ANALYZED` — mà `publish()` **không được gọi từ đâu** (xem câu 10). `features.md` mục 5/6 mô tả `ANALYZED` là tài liệu thiết kế, không phải hành vi code hiện tại.

---

## 6. Feature 6 (đề xuất chế tài) đã nối chưa?

**Chưa, và có 3 chỗ chặn riêng biệt.**

1. `build_recommend_agent()` (`src/features/answer/model/agent.py`) — chỉ được gọi trong `tests/test_answer.py`. `src/agents/case_graph.py` dừng ở `handoff → END`.
2. `answers.publish()` không có caller ngoài chính nó.
3. `answers._run_graph()` — chính là chỗ cần điền — hiện ném:

```python
raise AppError(501, "Agent đề xuất chế tài chưa gắn. Case agent chỉ trả message CaseHandoff.")
```

Phần **đã viết xong** và sẵn sàng dùng ngay khi nối:
- `layers.split_passages()` — xếp 4 tầng
- `decide.decide()` — chọn mức hoặc nâng rủi ro
- `draft.draft_answer()` — sinh prose
- `answers._store()` — ghi `recommendations` + `recommendation_citations`
- `answer/controller.py` — `GET /cases/{id}/answer`

Quy tắc xếp tầng (`layers.py`), lưu ý tầng cuối là **mặc định an toàn**:

| `policy_type` | Tầng |
|---|---|
| `INTERNAL_RULE` | `internal_rule` |
| `PRECEDENT` | `precedent` |
| `LAW` | `legal_basis` |
| `DECREE`, `CIRCULAR` | `legal_basis` — **trừ khi** code chứa `283/2026`/`283_2026`/`nd-283` hoặc tên có cả "xử phạt" + "hành chính" → `inspection_risk` |
| bất kỳ giá trị lạ / NULL | **`inspection_risk`** (không bao giờ thành chế tài) |

`decide.py` cố tình **không bao giờ trả `TERMINATION`**; `DISMISSAL` chỉ chốt khi `absence_days` có cả số ngày **và** cửa sổ (30/365) trong fact, và đoạn `INTERNAL_RULE` nhắc "sa thải".

---

## 7. Bỏ kho `legal_*` thì luồng hồ sơ có chạy không?

**Có.** Với `main` hiện tại: `src/features/**` và `src/agents/case_graph.py` không import `src.models.legal`, không import `src.services.hybrid_search`. Xóa 4 bảng `legal_*` + 4 migration (`0001`, `0002`, `0003`) + `scripts/{seed_legal,embed_legal,verify_db,verify_embeddings,eval_retrieval}.py` + `handoff/` + `data/chunk/` sẽ không làm hỏng một test nào.

Kiểm chứng: `pytest tests -q --noconftest` → **35 passed**.

Nhưng nó cũng không làm luồng hồ sơ *có chữ luật để trích*. `document_chunks` vẫn rỗng.

Cái mất đi: 1289 chunk, 1289 vector, 565 cạnh dẫn chiếu, và bộ đo `hybrid_search` chống hồi quy.

---

## 8. Nhánh `similarity` của cite — bao giờ chạy được?

**Hiện tại: không bao giờ. Có hai nguyên nhân độc lập, cùng đúng.**

**Nguyên nhân 1 — không ai gán `SearchQuery.embedding`.**
`SearchQuery.embedding` mặc định `None`. Grep toàn repo (`SearchQuery(`): `src/agents/case_graph.py:70` và `src/features/cite/model/graph.py:23` đều **không** truyền tham số này. Chỉ `tests/test_cite.py` truyền. `similarity_passages()` return `[]` ngay ở dòng đầu.

**Nguyên nhân 2 — hằng số sai sau migration `0002`.**

```python
# src/features/cite/model/similarity.py:11
EMBEDDING_DIM = 1536        # ← sai
```

Nhưng DB thật:

```
document_chunks.embedding  →  vector(1024)
disciplinary_decisions.embedding → vector(1024)
legal_chunk_embeddings.embedding → vector(1024)
```

Migration `0002_unify_mistral_embed` đã đổi 1536 → 1024 (`settings.EMBEDDING_DIMENSIONS = 1024`), nhưng `similarity.py` chưa được sửa theo. Nghĩa là **kể cả khi ai đó gán vector đúng 1024 chiều, nhánh này vẫn từ chối** (`len(query.embedding) != 1536` → `[]`).

Hai tài liệu cũng còn ghi 1536 và cần sửa cho khớp:
- `docs/features/features.md:351` — "Embed từng chunk, 1536 chiều"
- `docs/features/checklist-case-agent.md:50` — "vector 1536 chiều"

Cách sửa đúng: đổi `EMBEDDING_DIM` sang `settings.EMBEDDING_DIMENSIONS` (đọc từ `src/core/config.py`), rồi cho `retrieve_node` gán embedding từ `EmbeddingClient`. Nhưng lưu ý: `document_chunks` đang rỗng nên sửa xong vẫn không ra kết quả — vấn đề gốc vẫn là thiếu dữ liệu.

---

## 9. Hai bản `reciprocal_rank_fusion` khác nhau — đừng lẫn

| | cite | `hybrid_search` |
|---|---|---|
| file | `src/features/cite/model/rrf.py` | `src/services/hybrid_search.py` |
| đầu vào | `list[list[Passage]]` | `list[list[str]]` |
| k | `_RRF_K = 60` | `RRF_K = 60` |
| tie-break | **không có** → thứ tự dict, không tất định | sort `(-score, chunk_id)` → tất định |
| lexical arm | BM25 Python thuần trên content | `ts_rank` trong Postgres |

Hai hệ số khác nhau về hành vi. Nếu dev đọc "k=60" ở đây và kết luận "cùng thuật toán" thì sai — tie-break đã khác.

Tương tự: `RRF_K` của cite là 60 cố định, **không** phải tham số cấu hình; `hybrid_search` ghi rõ trong docstring rằng các hằng số đó là hợp đồng đóng băng, đổi là phải review + cập nhật changelog.

---

## 10. Nếu muốn cite trả về đoạn luật thật thì làm gì?

Yêu cầu tối thiểu, theo thứ tự:

**Bước 1 — có dữ liệu trong `document_chunks`.** Đây là nút thắt duy nhất. Cần một đường ghi:

```
policies (1 dòng / chính sách, policy_type = LAW | DECREE | CIRCULAR | INTERNAL_RULE | PRECEDENT)
  └─ policy_versions (status=ACTIVE, effective_from ≤ incident_date, effective_to ≥ hoặc NULL)
       └─ documents (ingest_status = CHUNKED | EMBEDDED)     ← bắt buộc, không có thì bị lọc
            └─ document_chunks (content, article, clause, point, chunk_index, section_title, metadata.article_title)
```

**Bước 2 — ánh xạ cây `legal_*` sang cây kia.** Chú ý khác biệt kiểu:

| | `legal_chunks` | `document_chunks` |
|---|---|---|
| PK | `TEXT` (`BLLD:CVIII:M01:A125:C01:P-a`) | `UUID` `gen_random_uuid()` |
| số điều | `article_number INTEGER` | `article VARCHAR(50)` |
| số khoản | `clause_number INTEGER` | `clause VARCHAR(50)` |
| điểm | `point_letter VARCHAR(16)` | `point VARCHAR(50)` |
| cấp | `chunk_level` (ARTICLE/CLAUSE/POINT) | không có cột cấp, suy từ NULL |
| breadcrumb | `header_context TEXT` | `section` + `section_title` |
| metadata | `meta JSONB` | `metadata JSONB` (tên cột là `metadata`) |
| thứ tự | không có cột thứ tự | `chunk_index` **UNIQUE per document** |
| vector | bảng riêng `legal_chunk_embeddings` | cột `embedding vector(1024)` trên chính dòng |

`chunk_index` là ràng buộc thật: `UNIQUE (document_id, chunk_index)`. Phải gán 0..N-1 liên tục khi insert, và Điều 125 chỉ có 1 chunk `ARTICLE` nên không map được theo khoản.

**Bước 3 — nội quy công ty.** `missing_internal_rule` chỉ về `false` khi có chunk với `policies.policy_type = 'INTERNAL_RULE'`. `legal_documents` **không có** dòng nào là nội quy (3 dòng đều là luật/nghị định), nên `document_chunks` copy từ kho legal **vẫn không đáp ứng** yêu cầu này.

**Bước 4 — ngày hiệu lực. Đây là phần tôi đã đánh giá sai, xem mục 14.**

`legal_documents` không có cột `effective_from`/`effective_to`, **nhưng dữ liệu ngày hiệu lực vẫn còn đủ trong repo và suy ra được.** Đo thật:

| Văn bản | Ngày hiệu lực | Nguồn trong repo |
|---|---|---|
| BLLD 45/2019/QH14 | **2021-01-01** | dòng đầu `data/markdown/2026_131_18_VBHN-VPQH.md` |
| ND 145/2020/NĐ-CP | **2021-02-01** | Điều 114 khoản 1 |
| ND 283/2026/NĐ-CP | **2026-09-10** | Điều 66 khoản 1 |

`legal_documents.amended_by` còn chứa `effective_date` theo từng footnote sửa đổi (mục 14).

Nói thẳng: **copy 1-1 vẫn không đủ**, nhưng danh sách thiếu đã ngắn lại từ 4 xuống 3. Cite còn thiếu `policy_type`, `internal_rule`, và `chunk_index`. Phần ngày hiệu lực thì lấy được từ dữ liệu có sẵn, không cần suy đoán.

---

## 11. Những thứ đang hỏng mà dev sẽ vấp ngay

### 11.1 App không import được — `src/api/routes.py` không tồn tại

```
.venv\Scripts\python.exe -c "import src.main"
ModuleNotFoundError: No module named 'src.api.routes'
```

`src/main.py:7` còn `from src.api.routes import router`. Commit `6217f7f` xóa `src/api/routes.py` và `src/api/__init__.py` (đổi tên sang `src/opencase/router.py`) nhưng `main.py` chưa được sửa. Thư mục `src/api/` giờ chỉ còn `__pycache__/routes.cpython-312.pyc` — **artifact của bản cũ, git không track**.

Hệ quả:
- `pytest tests -q` → **lỗi ngay ở conftest** (`from src.main import app`).
- `pytest tests -q --noconftest` → 35 pass, 3 error trong `tests/test_api/test_routes.py` (thiếu fixture `client`).
- `docker compose up backend` sẽ crash.

**Không router nào được mount.** Ba `controller.py` (`opencase`, `clarify`, `answer`) đều export `router` riêng, nhưng không có file nào `include_router` chúng. Health endpoint vẫn OK nếu sửa import.

Cách sửa: tạo lại `src/api/routes.py` gộp 3 router, hoặc sửa `main.py` import trực tiếp từ 3 controller.

### 11.2 `src/services/vector_store.py` cũng đã bị xóa

`src/agents/tools/example_tool.py:6` còn `from src.services.vector_store import get_vector_store`. File không tồn tại (xóa ở `6217f7f`). Import này chỉ nổ khi ai đó import `example_tool`. `src/agents/graph.py` không import nó nên template graph vẫn chạy.

### 11.3 `embedding` của `document_chunks` NULL toàn bộ

```
select count(*) from document_chunks where embedding is not null;  →  0
```

Index HNSW có predicate `WHERE embedding IS NOT NULL` nên với 0 dòng nó rỗng — **đây là hành vi đúng**, không phải index hỏng.

### 11.4 `docker compose` service `backend` không chạy được

Vì 11.1. `docker-compose.yml` vẫn khai báo `backend` với healthcheck gọi `/health`.

### 11.5 `violation_types` rỗng

`answers._link_violation()` gọi `ensure_violation(...)`; bảng có 0 dòng nên nó log `"violation type %s is not seeded"` và trả `False`. `publish()` vẫn chạy tiếp — chỉ là không gắn được `case_violations`.

---

## 12. Số đo nào trong log cũ đã cũ?

`conversation-legal-va-document-chunks.md` mục 7 ghi:

> "Alembic của database này dừng ở `04e5c85e7957`. Các bảng `legal_documents`, `legal_chunks`, `legal_chunk_embeddings` chưa được tạo trên database này."

**Sai.** Đo lại hôm nay:

```
version_num = 0003_legal_embeddings
legal_documents 3 · legal_chunks 1289 · legal_chunk_references 565 · legal_chunk_embeddings 1289
```

Phần đúng giữ nguyên: `policies` / `policy_versions` / `documents` / `document_chunks` đều **0 dòng**. Kết luận "cite trả về rỗng" vẫn đúng, chỉ là lý do đã khác — không phải vì bảng thiếu, mà vì **chưa có dòng nào trong nhóm `policies → document_chunks`**.

Mục 5 và 8 của file đó vẫn đúng. Mục 6 ("ví dụ người A nghỉ không phép") vẫn đúng ở mức kết quả, và tôi đã đo lại các con số trung gian ở câu 5.

---

## 13. Câu trả lời ngắn cho 5 câu hỏi hay gặp nhất

**"Cite đọc `legal_chunks` không?"**
Không. Nó đọc `document_chunks` qua `documents → policy_versions → policies`, lọc theo `incident_date`. Không có bất kỳ con trỏ nào giữa hai nhóm.

**"Bỏ `legal_*` có sao không?"**
Với runtime hồ sơ: không sao, không import gì từ đó. Mất đi 1289 chunk + 1289 vector + bộ đo chống hồi quy.

**"Làm sao để cite ra Điều 125?"**
`document_chunks` phải có dòng. Điều 125 hiện nằm ở `legal_chunks` với `chunk_id = 'BLLD:CVIII:M01:A125'`, cấp `ARTICLE`, không có khoản. Phải tạo chuỗi 4 bảng kia và ghi vào.

**"Hybrid search có dùng được không?"**
Dùng được, đo được: hybrid Hit@5 = 0,900, Article@5 = 1,000. Nhưng chỉ `scripts/eval_retrieval.py` và `scripts/verify_embeddings.py` gọi. Chưa có agent nào gọi — đó là B8.

**"Feature 6 xong chưa?"**
Logic xong (`layers` → `decide` → `draft` → `store`), nhưng `_run_graph()` ném 501 và `publish()` không có caller. Cần một commit nối, không phải viết mới.

---

## 14. Hiệu lực văn bản: dữ liệu CÓ, chỉ chưa nằm đúng chỗ

Bổ sung sau khi đào sâu `amended_by`. **Đây là phần làm giảm rào cản của cầu nối nhiều nhất.**

### 14.1 Ba ngày hiệu lực — lấy được từ repo

| Văn bản | `effective_from` | Nguồn |
|---|---|---|
| BLLD 45/2019/QH14 | **2021-01-01** | dòng đầu `data/markdown/2026_131_18_VBHN-VPQH.md` |
| ND 145/2020/NĐ-CP | **2021-02-01** | Điều 114 khoản 1 |
| ND 283/2026/NĐ-CP | **2026-09-10** | Điều 66 khoản 1 |

Cả ba đều **chưa hết hiệu lực** → `effective_to = NULL` cho cả 3.

⚠️ **Cảnh báo thời điểm.** Hôm nay là **29/09/2026**, ND 283 hiệu lực từ **10/09/2026**. Nghĩa là với `incident_date` trong ví dụ (`2026-03-01`), **ND 283 chưa có hiệu lực** và cite phải loại nó. Cùng một câu hỏi nhưng `incident_date = 2026-10-01` sẽ kéo ND 283 vào. Đây đúng là hành vi mong muốn — nhưng chỉ xảy ra nếu bước 4 cầu nối làm đúng, và là lý do không được hardcode `effective_from` cho cả 3 văn bản bằng một ngày chung.

### 14.2 `amended_by` có `effective_date` theo từng điều

5 footnote sửa đổi, mỗi footnote mang ngày hiệu lực riêng:

| footnote key | `effective_date` | `law_no` |
|---|---|---|
| `2` | 2026-01-01 | 124/2025/QH15 |
| `3` | 2026-01-01 | 124/2025/QH15 |
| `4` | **2026-07-01** | 113/2025/QH15 |
| `5` | 2026-01-01 | 71/2025/QH15 |
| `6` | 2026-01-01 | 71/2025/QH15 |

**Nhưng key là số thứ tự footnote, KHÔNG phải số điều.** Ánh xạ thật, đọc từ `document_tree_BLLD.json` qua trường `footnote_ids`:

| footnote | → Điều | Tiêu đề |
|---|---|---|
| `2` | Điều 59 | Đào tạo nghề nghiệp và phát triển kỹ năng nghề |
| `3` | Điều 61 | Học nghề, tập nghề để làm việc cho người sử dụng lao động |
| `4` | Điều 139 | Nghỉ thai sản |

Hai điều hết:

- **Footnote 5 và 6 không gắn được với điều nào.** `document_tree` chỉ có `footnote_ids` cho 59/61/139. Đây là **giới hạn thật của dữ liệu B3**, không phải lỗi truy vấn.
- **`legal_chunks.meta` KHÔNG chứa `footnote_ids`.** Kiểm tra `article_number in (59,61,139)` → `meta->'footnote_ids'` NULL cho tất cả. Liên kết footnote→điều **bị mất ở bước B4** khi seed. Nếu muốn lọc theo ngày sửa đổi ở tầng chunk thì phải đọc `document_tree_BLLD.json`, không đọc được từ DB.

### 14.3 Ảnh hưởng tới nghiệp vụ: không chặn vụ kỷ luật

Các điều bị sửa là **59, 61, 139** — đào tạo nghề, học nghề, thai sản. **Không điều nào thuộc Chương VIII về kỷ luật.**

Đối chiếu trực tiếp — các điều kỷ luật chính đều **không** nằm trong danh sách sửa đổi:

```
BLLD:CVIII:M01:A118   (nội quy lao động)
BLLD:CVIII:M01:A125   (sa thải khi tự ý bỏ việc)
BLLD:CVIII:M01:A127
BLLD:CVIII:M01:A122:C01..C06
BLLD:CXIV:M05:A201
```

**Kết luận thực tế:** với các vụ kỷ luật — thứ P-029 thực sự làm — hiệu lực theo từng điều **không phải rào cản**. Chỉ cần 3 ngày hiệu lực ở 14.1 là đủ cho toàn bộ use case hiện tại.

Phần sửa đổi theo điều chỉ cần xử lý khi mở rộng sang các điều 59/61/139, và khi đó phải đọc `document_tree_BLLD.json` vì DB đã mất liên kết.

### 14.4 Tóm lại: danh sách thiếu cho cầu nối

| # | Cite cần | Kho legal có? | Chi phí |
|---|---|---|---|
| 1 | `policy_type` | gián tiếp qua `document_type` | map 2 dòng |
| 2 | `effective_from/to` | **có, suy ra được** | hardcode 3 ngày (14.1) |
| 3 | `chunk_index` | không có | sinh tuần tự |
| 4 | `INTERNAL_RULE` | không có, và không thể có từ nguồn luật | feature riêng |

Từ "4 khoảng trống, một cái không lấp được" xuống "3 việc kỹ thuật + 1 feature riêng".
