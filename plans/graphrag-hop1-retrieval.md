# Kế hoạch: GraphRAG hop-1 — traverse đồ thị dẫn chiếu trong retrieval

## Context

Session trước (với OpenCode) đã dựng xong tầng dữ liệu đồ thị:
- `chunk_references` (migration `0011`): 599 cạnh dẫn chiếu `source_chunk_id → target_chunk_id` trên corpus sống (`document_chunks`), kèm `rule`, `confidence (HIGH/LOW)`, `needs_review`, index duyệt xuôi (`uq_chunk_references`) + ngược (`ix_chunk_references_target_source`).
- `scripts/copy_chunk_references.py`: ETL graph từ `legal_chunk_references` → `chunk_references`.

**Gap:** chưa có runtime nào traverse đồ thị. Retrieval (`src/features/cite/model/pipeline.py`) chỉ chạy similarity/bm25/lexical → RRF → rerank (pass-through) → fallback page_index, không đụng `chunk_references`.

**Phạm vi (đã chốt với user):** graph retrieval hop-1 trong pipeline retrieval. KHÔNG làm eval so sánh, không community detection, không đổi rerank scoring.

## Ý tưởng (giải thích đời thường)

**Một câu:** sau khi tìm được các điều luật "giống câu hỏi" bằng text search, ta lần theo bảng dẫn chiếu để kéo thêm những điều mà chúng viện dẫn tới — giống như đọc một điều luật xong thì bấm vào footnote "xem thêm Điều 34".

**Vì sao cần:** search hiện tại chỉ tìm chunk có chữ giống câu hỏi. Nhưng văn bản luật có tính "viện dẫn": Nội quy công ty viện dẫn Điều 125 BLLD, hoặc Điều 125 nói "theo khoản 2 Điều 34". Text search có thể tìm ra Nội quy nhưng **không bao giờ** tìm ra Điều 125 nếu câu hỏi không nhắc tới nó — trong khi đó lại chính là "căn cứ bắt buộc". Đồ thị đã ghi sẵn 599 quan hệ viện dẫn đó; việc còn lại là **đọc nó lúc truy vấn**.

**Ví dụ cụ thể:**
- Nhân viên tự ý nghỉ 5 ngày → query là mô tả sự kiện.
- Search text trả về top: chunk Nội quy HRCorp về "tự ý nghỉ".
- Nhìn bảng `chunk_references`: chunk Nội quy đó có mũi tên trỏ sang "Điều 125 BLLD".
- Graph expand kéo Điều 125 BLLD vào danh sách ứng viên, dù text search mù tịt về nó.
- Kết quả cuối có cả Nội quy **và** căn cứ luật đi kèm.

**Luồng chạy, kể bằng lời:**

1. **Tìm bình thường (đã có sẵn).** Ba nhánh similarity / BM25 / lexical chạy song song, gộp lại thành 1 danh sách xếp hạng. Gọi danh sách này là `fused`.
2. **Chọn "hạt giống".** Lấy 5 chunk đứng đầu `fused` làm điểm xuất phát (seed) — những thứ chắc chắn liên quan.
3. **Đi 1 bước trên đồ thị.** Với mỗi seed, tra bảng `chunk_references` hỏi 2 câu: *"chunk này viện dẫn tới điều nào?"* (đi xuôi) và *"điều nào viện dẫn tới chunk này?"* (đi ngược). Chỉ đi 1 bước (hop-1), không lan vô tận.
4. **Lọc cho sạch.** Bỏ cạnh `confidence=LOW` (dẫn chiếu mơ hồ), cạnh bị gắn cờ `needs_review`, và cạnh trỏ ra văn bản ngoài corpus (Luật BHXH, Công đoàn… — không có chunk để kéo). Chỉ nhận neighbor còn **hiệu lực tại ngày vi phạm**.
5. **Trộn vào danh sách.** Neighbor mới nhét vào cùng `fused`, nhưng **điểm thấp hơn** (điểm seed tốt nhất × 0.6) để chunk tìm bằng text vẫn xếp trước khi hòa. Chặn trần 12 neighbor để không ngập kết quả. Trùng với chunk đã có thì bỏ qua.
6. **Xếp hạng lần cuối.** Danh sách trộn đi qua rerank rồi trả ra hits.

**Hai chỗ dễ thắc mắc:**

- **Sao không làm nhánh thứ 4 chạy song song như 3 nhánh kia?** Vì graph không có "câu hỏi" riêng — nó phải có kết quả của 3 nhánh kia làm hạt giống mới biết bắt đầu từ đâu. Nên nó bắt buộc chạy **sau** khi gộp.
- **Sao chèn ngay sau khi gộp, trước rerank?** Vì lúc đó đã có danh sách sơ bộ để làm seed, và rerank là công đoạn sắp xếp cuối — đẩy neighbor vào trước rerank thì chúng được sắp chung một lượt.

**Thuật ngữ dịch ra tiếng người:** `seed` = chunk xuất phát; `hop-1` = đi đúng 1 bước; `in-force filter` = chỉ lấy văn bản còn hiệu lực tại ngày sự kiện; `decay 0.6` = giảm điểm neighbor; `RRF` = thuật toán gộp điểm 3 nhánh search; `origin="graph"` = nhãn đánh dấu hit này đến từ graph để truy vết.

## Thiết kế

**Kiến trúc chọn: node `expand` giữa `rrf` và `rerank`.**

Lý do (không chọn arm thứ 4): graph không có query riêng — nó phải traverse từ seed là output của các arm khác, nên chạy song song 4 arm là sai dependency. Node expand sau RRF có fused top-k làm seed tự nhiên, và seam `rerank.py` (đang pass-through) sẽ tự động sắp xếp lại khi về sau gắn cross-encoder.

Luồng mới:
```
START ─┬─► similarity ─┐
       ├─► bm25 ───────┼─► rrf ─► expand ─► rerank ─► [hits?] ─► END
       └─► lexical ────┘                            └─► page_index (nếu rỗng)
```

**Nguyên tắc hoạt động của `expand`:**
1. Lấy top `GRAPH_SEED_K=5` của `fused` làm seed.
2. Truy vấn `chunk_references` 1 hop cả 2 chiều: outgoing (`source_chunk_id IN seeds`) và incoming (`target_chunk_id IN seeds`) — "khoản này dẫn tới đâu" + "điều này được ai trích dẫn".
3. Bộ lọc cạnh: chỉ đi `confidence='HIGH'` và `needs_review=false` (cạnh LOW/BOUNDARY là loại mơ hồ — loại khỏi v1 để output predictable; hằng số `GRAPH_MIN_CONFIDENCE` để mở lại sau).
4. Bỏ `target_chunk_id NULL` (63 cạnh external — không có chunk đích để traverse).
5. Neighbor phải sống sót qua in-force filter theo `incident_date` (tái dùng `_candidate_stmt`/`in_force_filter` trong `store.py`) — giữ nguyên bất biến "chỉ trả văn bản còn hiệu lực tại ngày vi phạm".
6. Dedup với fused theo chunk id (đã có trong fused thì giữ nguyên vị trí/điểm).
7. Gán điểm neighbor = điểm seed tốt nhất × `GRAPH_EDGE_DECAY=0.6`, merge + sort ổn định (fused thắng khi hòa điểm), cap `GRAPH_MAX_EXPANSION=12`.
8. Fail-isolation kiểu `_arm()`: lỗi graph → trả fused nguyên vẹn, retrieval không bao giờ chết vì graph.

**Provenance/audit:** neighbor gắn `origin="graph"` trên `Passage` (ledger `save_retrievals` phân biệt được hit đến từ graph); `retrieval` mode vẫn là `"hybrid"` khi có hits.

## Kiến trúc nội bộ khối `expand`

Bước duyệt đồ thị gồm 6 khối nối nhau, mỗi khối một trách nhiệm:

```
fused (top-k từ RRF)
   │
   ├─(1) seed_selector     → [chunk_id × 5]
   ├─(2) edge_reader       → cạnh thô (source, target, rule, confidence), 2 chiều
   ├─(3) edge_filter       → bỏ NULL target / LOW / needs_review
   ├─(4) neighbor_hydrate  → lấy nội dung + lọc còn hiệu lực theo incident_date
   ├─(5) score_merge       → decay điểm, dedup, cap 12
   └─► expanded ─► rerank ─► hits
```

**Mô hình đồ thị:** node = chunk trong `document_chunks`; cạnh = dòng `chunk_references`, **có hướng** (A viện dẫn B) và **có nhãn** (`rule`, `confidence`). 1377 node / 599 cạnh → đồ thị rất thưa (degree ra trung bình < 0.5), nên hop-1 chỉ thêm vài node, không bùng nổ. Trừ 63 cạnh external (target NULL), phần duyệt được là ~536 cạnh nội bộ giữa 4 văn bản.

**(1) seed_selector** — 5 chunk đầu của `fused` (lấy id + điểm). Không lấy nhiều vì seed rác kéo neighbor rác; tinh chỉnh bằng ngưỡng điểm tối thiểu nếu cần.
**(2) edge_reader** — 2 truy vấn SQL: xuôi `source_chunk_id = ANY(seeds)` (index `uq_chunk_references`), ngược `target_chunk_id = ANY(seeds)` (index `ix_chunk_references_target_source`). Quyết định kiến trúc: đọc thẳng SQL thay vì nạp cả đồ thị vào RAM — để lọc in-force ngay trong câu truy vấn và tránh cache cũ khi corpus rebuild (re-seed sinh UUID mới nên cache sẽ trỏ sai).
**(3) edge_filter** — lọc tại tầng cạnh (rẻ nhất): bỏ `target_chunk_id IS NULL` (external), `confidence='LOW'`, `needs_review=true`.
**(4) neighbor_hydrate** — lấy nội dung neighbor và JOIN qua `_candidate_stmt` + `in_force_filter(incident_date)`. Mấu chốt nghiệp vụ: văn bản được viện dẫn có thể đã hết hiệu lực tại ngày vi phạm (vd NĐ 145 hết hiệu lực 09/09/2026) → không kéo vào. Đây là lý do graph phải nằm trong pipeline retrieval, không phải công cụ tra cứu riêng.
**(5) score_merge** — gộp cạnh/seed trùng; điểm = `max(điểm seed) × 0.6` (tin ít hơn kết quả search trực tiếp → chunk text thắng khi hòa); dedup với `fused`, cap 12, sort ổn định.
**(6) Provenance** — neighbor mang `origin="graph"` + giữ thông tin cạnh (được điều nào viện dẫn), phục vụ audit ledger.

**Vì sao đặt sau `rrf`, trước `rerank` (không phải sau rerank):** rerank là bước sắp xếp cuối và chốt danh sách trả ra. Expand sau rerank thì neighbor mới bị append thô, không được sắp lại và rơi ngoài top-k đã cắt. Đặt trước rerank để neighbor được trộn rồi sắp chung một lượt.

## Thay đổi theo file

### 1. `src/features/cite/model/store.py` (mới — truy vấn)
- Thêm `fetch_graph_neighbors(session, incident_date, seed_chunk_ids, limit)`:
  - Query `ChunkReference` (`src/models/chunk_references.py`, đã đăng ký trong `src/common/orm.py`) 2 chiều theo 2 index sẵn có.
  - Collect neighbor ids (bỏ NULL target, lọc `confidence='HIGH' AND needs_review=false`), JOIN `document_chunks` qua `_candidate_stmt(incident_date)` để tôn trọng in-force.
  - Trả về `list[Passage]` qua `to_passage`, đánh dấu `origin="graph"`.

### 2. `src/features/cite/model/graph_expand.py` (mới — logic thuần)
- Hằng số: `GRAPH_SEED_K=5`, `GRAPH_MAX_EXPANSION=12`, `GRAPH_EDGE_DECAY=0.6`, `GRAPH_MIN_CONFIDENCE="HIGH"`.
- `expand_passages(fused: list[Passage], neighbors: list[Passage]) -> list[Passage]`: dedup + decay score + merge sort + cap — hàm thuần, dễ test.
- Node helper `expand_node(session)` bọc try/except kiểu `_arm`.

### 3. `src/features/cite/model/pipeline.py` (wire vào graph)
- `RetrievalState`: thêm channel `expanded: list[Passage]` (giữ `fused` nguyên cho debug).
- `compile_retrieval(similarity, bm25, lexical, page_index=None, expand=None)`: thêm node `expand` (mặc định pass-through để không phá test cũ), đổi edge `rrf→rerank` thành `rrf→expand→rerank`.
- `rerank_node`: dùng `state.get("expanded") or state.get("fused")` — contract `rerank(query, passages)` giữ nguyên (seam cross-encoder tương lai không đổi).
- `build_retrieval_graph`: truyền `expand_node(session)` thật.

### 4. `src/features/cite/model/page_index.py` / `search.py` (audit nhẹ)
- Đảm bảo `retrieval_mode()`/ledger chấp nhận `origin="graph"` của passages (mở enum nếu cần), không đổi behavior khác.

### 5. Tests — `tests/test_graph_expand.py` (mới) + chỉnh nhẹ `tests/test_cite.py`, `tests/test_pipeline.py`
- Unit `expand_passages`: dedup, decay score, cap, fused thắng khi hòa.
- Wiring: `compile_retrieval` với fake nodes — thứ tự `rrf→expand→rerank`, không truyền expand thì pass-through.
- Store (fixture DB theo pattern `tests/conftest.py`/`test_cite.py`): 2 chiều traversal, bỏ target NULL, bỏ cạnh `needs_review`, neighbor hết hiệu lực theo `incident_date` không được mở rộng, fail → fused nguyên vẹn.

### 6. Docs — cập nhật giai đoạn ingestion (data pipeline)
- `data_pipeline_steps/README.md`:
  - B5 (dòng ~57–60): bổ sung "đã có runtime đọc đồ thị (node `expand`)" thay vì chỉ mô tả như tiềm năng.
  - Khối B7/B8 (dòng ~70–82): ghi rõ graph hop-1 giờ nằm trên **đường retrieval thật** `cite/model/pipeline.py`.
  - Bảng tổng (dòng ~26): ghi chú B5 đã được tiêu thụ ở runtime.
- `docs/qa-legal-va-document-chunks.md:227`: sửa *"Không runtime nào đọc bảng này"* → có node `expand` đọc.
- `docs/conversation-legal-va-document-chunks.md:35`: sửa *"Search không đọc bảng này"*.

### 7. Docs — kiến trúc
- `ARCHITECTURE.md` dòng ~331: sửa `Cross-reference graph — none` → mô tả runtime hop-1 traversal qua `chunk_references`.

**Không đổi ở giai đoạn ingestion:** code pipeline (`data_pipeline_steps/step*/`), ETL (`scripts/seed_*.py`, `scripts/copy_chunk_references.py`), và dữ liệu DB (không migration, không re-seed). Đây là consumer mới của dữ liệu đã có.

## Không làm (out of scope)
- Eval so sánh baseline vs graph (B8) — để giai đoạn sau; `eval/minutes_golden.json` + `scripts/verify_minutes_golden.py` (đang untracked) sẽ là nền cho lần đo sau.
- Community detection / global GraphRAG, cross-encoder rerank thật, đổi embedding model.

## Giới hạn hiện tại & hướng phát triển tương lai

**Giới hạn của v1 (cố ý, không phải bug):**
- Đồ thị chỉ có **1 loại cạnh: "viện dẫn"**. Quan hệ "sửa đổi/thay thế/kế thừa" đang ở cấp văn bản (`legal_documents.amended_by`), chưa thành cạnh chunk.
- Chỉ **1 hop**.
- Cạnh `confidence='LOW'` bị **bỏ hẳn**.
- `GRAPH_EDGE_DECAY=0.6`, `GRAPH_SEED_K=5`, `GRAPH_MAX_EXPANSION=12` là số **tune tay**, chưa có cơ sở đo.
- Seed cố định top-5, chưa lọc theo ngưỡng điểm hay đa dạng nguồn.
- 63 cạnh external (target NULL) **không duyệt được** — chưa có chunk cho văn bản ngoài corpus (Luật BHXH, Công đoàn…).
- Rerank vẫn pass-through → neighbor chưa được chấm lại ngữ nghĩa.
- **Chưa có eval (B8)** để so baseline vs graph.

**Hướng phát triển:**
- Mở rộng **loại cạnh** (sửa đổi/thay thế/kế thừa) hoặc dẫn xuất từ `amended_by` → đồ thị giàu ngữ nghĩa hơn.
- **Hop-2 có kiểm soát** / personalized PageRank khi corpus lớn hơn.
- Đưa cạnh **LOW vào với hệ số phạt** thay vì loại bỏ.
- **Tune tham số bằng eval** thay vì đoán (decay, seed_k, cap).
- Gắn **cross-encoder rerank thật** → neighbor được chấm lại, giảm phụ thuộc vào decay.
- **Seed theo ngưỡng/đa dạng** thay vì top-5 cứng.
- Bổ sung chunk cho **văn bản ngoài corpus** để nối các cạnh external.
- **Cache đồ thị** nếu corpus lớn (đánh đổi với độ tươi của dữ liệu).
- Xa hơn: **community detection / global GraphRAG** cho câu hỏi tổng hợp.

## Verification
1. `make lint` (ruff) + `make test` (pytest) — toàn bộ test cũ phải xanh (đặc biệt `tests/test_cite.py`, `tests/test_pipeline.py`).
2. Test mới `tests/test_graph_expand.py` xanh.
3. Smoke thật với DB handoff: chạy 1 truy vấn qua `search_policies()` với incident_date hợp lệ, xác nhận hits có `origin="graph"` khi láng giềng liên quan tồn tại; EXPLAIN truy vấn neighbor dùng index (`uq_chunk_references` / `ix_chunk_references_target_source`).
4. Chạy `scripts/corpus_expectations.py` để chắc corpus không bị ảnh hưởng (599 cạnh/1377 chunk giữ nguyên).
