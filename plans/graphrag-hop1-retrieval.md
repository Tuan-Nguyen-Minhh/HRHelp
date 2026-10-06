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

### 6. Docs (nhẹ)
- `ARCHITECTURE.md` dòng ~331: sửa "Cross-reference graph — none" → mô tả runtime hop-1 traversal qua `chunk_references`.
- `data_pipeline_steps/README.md`: cập nhật B5 đã có runtime đọc đồ thị.

## Không làm (out of scope)
- Eval so sánh baseline vs graph (B8) — để giai đoạn sau; `eval/minutes_golden.json` + `scripts/verify_minutes_golden.py` (đang untracked) sẽ là nền cho lần đo sau.
- Community detection / global GraphRAG, cross-encoder rerank thật, đổi embedding model.

## Verification
1. `make lint` (ruff) + `make test` (pytest) — toàn bộ test cũ phải xanh (đặc biệt `tests/test_cite.py`, `tests/test_pipeline.py`).
2. Test mới `tests/test_graph_expand.py` xanh.
3. Smoke thật với DB handoff: chạy 1 truy vấn qua `search_policies()` với incident_date hợp lệ, xác nhận hits có `origin="graph"` khi láng giềng liên quan tồn tại; EXPLAIN truy vấn neighbor dùng index (`uq_chunk_references` / `ix_chunk_references_target_source`).
4. Chạy `scripts/corpus_expectations.py` để chắc corpus không bị ảnh hưởng (599 cạnh/1377 chunk giữ nguyên).
