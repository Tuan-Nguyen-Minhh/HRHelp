# CHANGELOG — P-029 Pipeline Fix (docx → markdown → chunks, 3 văn bản)

_Ngày: 2026-09-27. Nguyên tắc: 3 văn bản (BLLD 18/VBHN-VPQH, NĐ145/2020, NĐ283/2026)
là dữ liệu nền NGANG NHAU cho agent xử lý VPHC lao động — sửa/verify đồng đều,
không xếp P0/P1/P2 giữa các văn bản. Mọi lỗi cùng loại phát hiện ở bất kỳ văn bản
nào đều xử lý đồng thời cả 3._

## 1. target_doc greedy + trỏ sai văn bản (mục 1)

**Vị trí (đã verify, cả 3 văn bản):**
- BLLD:CXVII:M00:A219:C01/C02 (target_doc lẫn câu dài + trỏ sai 18/VBHN-VPQH cho
  Điều 54/55 vốn thuộc Luật BHXH)
- ND145_2020:CVIII:M00:A070:C03/C04 (`Bộ luật Lao độ […]` truncate từ envelope)
- ND283_2026:CIII:M00:A043/A044/A045/A046/A048, CIV:M00:A049/A052, CVI:M00:A066
  (nuốt `theo/khi/và/nhưng…` + `:` + newline)

**Bằng chứng trước:**
- BLLD C02: `Luật này nghỉ việc…:\na) Có tuổi… Điều 169 của Bộ luật` (HIGH, EXPLICIT)
- ND145 C03: `Bộ luật Lao độ […]")\nNội dung…` (HIGH, EXPLICIT)
- ND283 A044:C01: `Luật Bảo hiểm xã hội theo một trong các mức sau đây:\na) Từ 6`
  (HIGH, EXPLICIT); A066 LIST_EXPANSION: `của Nghị định này có hiệu lực…`
- Tổng invalid (>40/colon/newline): BLLD 1, ND145 2, ND283 16 (16 gồm cả long-law
  + greedy).

**Cách sửa (`cross_reference_resolver.py`):**
- `QUALIFIER_RE` bỏ lookahead `\s`, cho phép `,` (giữ `Luật An toàn, vệ sinh lao
  động`), greedy 80 ký tự + `_clean_law_name()` cắt tại `:`, newline, `;`, `,`
  (sau allowlist), từ nối `theo/khi/và/nhưng/mà/trong/với/để/không/chưa/đã/kể/có/cho…`,
  `.`; known-prefix trước (`Luật An toàn, vệ sinh lao động`, `Luật NLD VN đi làm
  việc ở NN theo HĐ` 67 ký tự allowlist, `Bộ luật Lao động`, `Luật BHXH`…).
- `_nearest_qualifier_after(body, mention_end, 100)`: chỉ lấy qualifier ≤100 ký tự
  NGAY SAU mention; nếu có `Điều Y` khác chen giữa → bỏ qua (tránh Điều 2 nhận
  nhầm `của Bộ luật` của Điều 169; tránh Điều 54 nhận nhầm của Điều 169).
- Body-only sentence (header_len) + width 500: tránh nhiễm header truncate `[…]`.
- Quoted-external: `_detect_quoted_external()` tìm `Sửa đổi, bổ sung … Luật X … “`
  → span; fallback Điều 219 BLLD + `bảo hiểm xã hội` → default BHXH; trong quote
  KHÔNG áp DEFAULT_SELF/EXPLICIT_SELF; `Luật này` độc lập (không phải `Bộ luật này`)
  trong quote → BHXH (`QUOTED_EXTERNAL`); explicit `của Bộ luật Lao động` trong
  quote vẫn giữ BLLD (vd Điều 169).
- Phân biệt `Luật này` vs `Bộ luật này` (`_has_standalone_luat_nay`); `Bộ luật`
  cụt (truncate window) → invalid → LOW.
- `_resolve_named()` ưu tiên số hiệu trong RAW (`92/2015/QH13` → TC9).
- Confidence: `>40` (trừ allowlist long-law) hoặc chứa `\n`/`:` → LOW
  (`EXPLICIT_LOW`/`AMBIGUOUS_LUAT_NAY`/`BOUNDARY_CHECK`); `Bộ luật` cụt → LOW.

**Bằng chứng sau (cùng 1 lần chạy verify):**
- Invalid target (>40/colon/newline, trừ allowlist): BLLD 0, ND145 0, ND283 0
  (10 long-law 67 ký tự giữ HIGH có allowlist, đã ghi rõ).
- BLLD A219:C02: Điều 2 → `Luật Bảo hiểm xã hội` (QUOTED_EXTERNAL, HIGH);
  Điều 169 → `18/VBHN-VPQH` (EXPLICIT, HIGH).
- ND145 A070:C03/C04: → `18/VBHN-VPQH` (EXPLICIT, HIGH), hết truncate.
- ND283 A044:C01: → `Luật Bảo hiểm xã hội` (HIGH); A066 LIST → `283/2026/NĐ-CP`
  (HIGH); A049/A052 long-law → full 67 ký tự HIGH (đúng tên luật).
- Tổng refs: BLLD 125 (HIGH 125), ND145 233 (HIGH 231, LOW 2 BOUNDARY hợp lệ),
  ND283 207 (HIGH 206, LOW 1 BOUNDARY hợp lệ). LOW còn lại đều là BOUNDARY_CHECK
  suy luận yếu (Điều > max_article → BLLD), có trong `low_confidence_refs.json`.

## 2. Số khoản/điểm dính liền (mục 2)

**Vị trí:**
- BLLD Điều 7 L128 `2.Người sử dụng…`, Điều 6 `đ)Tham gia…` (điểm dính), Điều 61
  `3.3[[3]]` (kèm footnote)
- ND145 Điều 32 L625 `2.Định kỳ…`, Điều 107 L2042 `3.Giải quyết…`
- ND283: quét toàn bộ 2472 dòng, không phát hiện stuck đầu dòng (đã quét như nhau).

**Đối chứng .docx:** `python-docx` BLLD para 71/72 là 2 paragraph riêng
(`1. Quan hệ…`, `2. Người sử dụng…`); lỗi do MarkItDown mất space (raw `.md`
đã có `2.Người…`, `đ)Tham gia…`).

**Cách sửa (`step2_preprocessing.py::fix_markitdown_spacing`, gọi trong
`pre_clean_text` cho cả 3 file):**
- `^(\s*\d+[a-z]?\.)([A-ZÀ-Ỹ…\[])` → chèn space; `^(\s*[a-zđ]\))([^\s])` → chèn space.

**Bằng chứng sau:** quét `^\d+\.[^\s]` + `^[a-zđ]\)[^\s]` trên cả 3 cleaned `.md`:
BLLD 0, ND145 0, ND283 0. Điều 7/32 hiển thị `2. Người…`/`2. Định kỳ…` đúng.
`CLAUSE_NUMBER_GAP` toàn cục 11 → 0 (triệt tiêu); flagged BLLD 22→20, ND145 27→19.

## 3. Footnote marker dính (mục 3)

**Vị trí (BLLD duy nhất, đã kiểm tra ND145/ND283 không dùng hệ footnote này):**
- L832 `a)2[[2]]`, L850 `3.3[[3]]`, L1782 `1.4[[4]]`, L1991 `8a.5[[5]]`,
  L2798 `THI HÀNH6[[6]]` (raw MarkItDown đã dính).

**Cách sửa (`fix_markitdown_spacing` + `hierarchy_parser._strip_md_inline`):**
- Xóa số lẻ trước anchor (`a)2[[2]]` → `a) [[2]]`), `**6**[[6]]` → ` [[6]]`,
  đảm bảo space trước/sau anchor (`\S[[` → ` [[`, `](...)X` → `](...) X`).
- Title strip: footnote anchor trong title xóa hẳn (tránh `THI HÀNH6`).

**Bằng chứng sau:** `\S\[\[` trên cleaned BLLD = 0; 5 vị trí đều `a) [[2]]`,
`3. [[3]]`, `1. [[4]]`, `8a. [[5]]`, `THI HÀNH [[6]]`. ND145/ND283 0 anchor
(đúng, không hệ footnote). Chunker `split_merged_footnote` giữ nguyên.

## 4. Heading merge (mục 4)

**Vị trí:**
- BLLD Điều 3 (`Giải thích từ ngữ Trong… như sau:`), Điều 99, Điều 120
  (`…bao gồm:`) — phát hiện thêm Điều 120 cùng loại, đã sửa đồng thời.
- ND145 Điều 69 (`…được quy định như sau:`), Điều 75 (`…được xác định như sau:`).
- ND283: quét toàn bộ headings với triggers (`như sau`, `bao gồm`, `được hiểu/
  quy định/xác định`, kết `:`) → 0 hit (không giả định, đã quét như 2 văn bản kia).

**Gốc:** raw MarkItDown đúng (`**Điều 3. Giải thích từ ngữ**` + dòng chapeau
riêng); `step2._collect_wrapped_title` gộp nhầm dòng `<80 ký tự, không kết `.``,
kể cả dòng kết `:` (chapeau).

**Cách sửa:** `_is_chapeau_line()` (trigger hoặc kết `:`) → break, không gộp;
`clause_start_pat` nới lỏng nhận cả marker thiếu space để không gộp khoản vào title.

**Bằng chứng sau:** headings trigger trên 3 cleaned = 0. Điều 3/99/120/69/75 đều
`#### Điều N. <title>` + dòng chapeau riêng + blank-line. Parser
`disambiguate_title_chapeau` giữ nguyên (dự phòng).

## 5. Trùng Chương XI ND145 (mục 5) — chỉ xác nhận

- `.docx` gốc đã trùng `Chương XI` (không phải lỗi convert). `ChapterTracker`
  canonical `XI→XII` + flag `DUPLICATE_CHAPTER_NUMBER` giữ nguyên, KHÔNG sửa logic.
- Sau regenerate: 17 chunks `ND145_2020:CXII…` mang flag, `step3_stats.tree_anomalies`
  vẫn `CHUONG XI: DUPLICATE_CHAPTER_NUMBER:XI-> XII`. Verify DAT.

## 6. Điều 219 BLLD lồng khoản/điểm trích luật khác (mục 6) — MỨC TẠM THỜI

**Hiện tượng:** Điều 219 trích nguyên văn Điều 54/55/73 BHXH… mỗi Điều trích có
khoản/điểm riêng → `OUT_OF_SEQUENCE_CLAUSE_NUMBER` (20) + `REPEATED_POINT_LETTER`
(C1/C4 20).

**Cách sửa (tạm thời, ghi rõ):** chưa tách cây hoàn toàn; thêm
`ChunkMetadata.is_quoted_external_text: bool` (`chunking_engine._make_chunk`:
BLLD Điều 219 + (`sửa đổi, bổ sung`/`bảo hiểm xã hội`/`“`) → True; generic
`sửa đổi… + quote` cho văn bản khác). 20/20 chunks Điều 219 mang flag True;
cross-ref trong quote trỏ đúng BHXH (`QUOTED_EXTERNAL`, mục 1), không dùng nhầm
`khoản N Điều 219`.
- Mức độ: **tạm thời** (chưa tách subtree riêng cho từng Điều được trích;
  clause/point numbering vẫn audit bằng OUT_OF_SEQUENCE/REPEATED như trước).
  Lý do: tách đầy đủ cần thay đổi hierarchy_parser + chunk_id scheme, vượt phạm vi
  lần này; metadata + refs đã đủ để agent không dùng nhầm.

**Bằng chứng:** `is_quoted_external_text=true`: BLLD 20, ND145 0, ND283 0.
OUT_OF_SEQUENCE còn 20 (toàn Điều 219, có lý do cụ thể, không `không rõ`).

## Ngoài phạm vi (DUY NHẤT)

- Bảng công thức lương Điều 54-57 NĐ145 (gồm placeholder `MISSING_FORMULA_IMAGE`
  Điều 56 + nội dung Điều 55/57): **KHÔNG xử lý**, vì agent xử lý VPHC lao động
  không dùng công thức lương. Giữ flag `MISSING_FORMULA_IMAGE` (1 chunk
  `ND145_2020:CVI:M02:A056`) để audit. Đây là loại trừ duy nhất.

## Phụ lục — Deep sweep lỗi tiềm tàng (2026-09-27, sau verify a–f)

- Unit: step2 14 passed, step3 golden 9 passed (TC9 số hiệu `92/2015/QH13` giữ đúng).
- Tree↔chunks khớp 100% (BLLD 220, NĐ145 115, NĐ283 68; chunk-cover đủ).
- Clause/point đích tồn tại: 1 case `ND145 A114 P-c → BLLD Điều 54 khoản 3`
  trỏ đúng luật (BLLD, EXPLICIT HIGH) nhưng khoản 3 không tồn tại trong BLLD
  hợp nhất 2019 (Điều 54 chỉ có khoản 1–2). Nguyên nhân version-drift: nguồn dẫn
  `NĐ 29/2019 thi hành khoản 3 Điều 54 BLLD 2012 (cũ)`. Giữ HIGH (định danh luật
  đúng), ghi nhận drift, không hạ LOW.
- `parent_chunk_id` treo 1030 chunk (CLAUSE/POINT trỏ ARTICLE id không tồn tại khi
  Điều tách nhỏ): thiết kế gốc (`chunking_engine._make_chunk` luôn set parent về
  ARTICLE id), tồn tại trước fix, giữ nguyên để tránh đổi schema/chunk_id.
- Token over-limit đều có flag `POINT_BODY_OVER_LIMIT`; `NEEDS_MANUAL_REVIEW` đều
  kèm flag `FOOTNOTE_*`; mid-line multi-clause merge 0/0/0. Log chi tiết:
  `data/chunk/deep_sweep.log`.

## Artifacts (cùng 1 pipeline run)

- `data/cleaned_markdown/*.md` (3 file, 220/115/68 Điều, SUCCESS).
- `data_pipeline_steps/step3/output/document_tree_*.json`, `chunks_*.json`
  (BLLD 381, ND145 377, ND283 531; tổng 1289 vs 1290, chênh -1 có lý do per-doc:
  BLLD +1 do tách heading, ND145 -2 do gọn chunk, ND283 giữ nguyên),
  `step3_stats.json`, `validation_report.md` (per-doc), `low_confidence_refs.json`
  (3 LOW BOUNDARY hợp lệ).
- `references_sample_review.md/.csv` (60 mẫu, 20/văn bản, stratified theo rule).
- `verify_final.log` (lần chạy cuối DAT a-f cùng lúc).
- Tests: `step2` 14 passed, `step3 golden` 9 passed (TC9 law-number giữ đúng).
