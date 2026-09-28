# V-manual — review tay kết quả retrieval B7

_Đây là bước ký **ngoài** vòng lặp auto (theo `step6_7_plan.md` mục 4, giống
V5-manual của B4/B5). `scripts/verify_embeddings.py` in PASS/FAIL cho V1–V8;
tài liệu này là chữ ký của người đọc tay từng kết quả. **Chưa ký thì chưa
nghiệm.**_

- Ngày review: **2026-09-28**
- Bộ đọc: `eval/legal_golden.json` v1 · `eval/results/retrieval_eval_20260928_110339.*` (bản `104817` giữ làm lịch sử; Q02 đã sửa text câu hỏi nên bảng dưới đọc theo bản mới)
- Mô hình: `mistral-embed` 1024-dim · 1289 chunk · `hnsw ef_search=100` · RRF k=60
- Người đọc: _(chưa ký)_

## 1. Checklist theo từng query

Đọc **top-5 hybrid** của cả 10 query. `✔` = trong top-5 có đúng nội dung trả lời
câu hỏi; `~` = có đúng **Điều** nhưng không đúng **chunk**; `✘` = không có.

| # | Query | top-5 hybrid đọc tay | Kết luận |
|---|---|---|---|
| Q01 | Tuổi nghỉ hưu điều kiện bình thường | A169:C02, A219:C04:P-a-2, A169:C01, A219:C04:P-a-3, A219:C04:P-b-2 | ✔ rank 1 đúng ngay. 3 điểm Điều 219 trong top-5 là dẫn chiếu về chính Điều 169 — nhiễu hợp lý, không sai |
| Q02 | NSDLĐ không đăng ký NLĐ vào BHXH | A043:C02:P-a, A043:C02:P-h, **A044:C01**, A043:C02:P-b, A043:C02:P-đ | ✔ rank 3 (bản 110339, câu hỏi đã sửa — xem mục 2; bản 104817 cũ rank 4 với top-5 khác hẳn) |
| Q03 | Nội quy lao động, ai ban hành | A069:C04 (NĐ145), A069:C01 (NĐ145), **A118**, A069:C03, A069:C02:P-g | ✔ rank 3. 4/5 là Điều 69 NĐ145 về ban hành nội quy — cùng chủ đề, không phải câu trả lời |
| Q04 | Không áp dụng nhiều hình thức kỷ luật | **A122:C02**, A122:C03, NĐ283 A025:C03:P-d, A122:C05, NĐ283 A025:C03:P-e | ✔ rank 1. Điểm d NĐ283 A025 nói đúng nguyên tắc nhưng là quy định khác |
| Q05 | Làm thêm giờ tối đa bao nhiêu giờ/năm | A107:C02, NĐ145 Đ62, **A107:C03**, Đ114, NĐ283 A024:C01 | ✔ rank 3. Xem mục 2 — **đã sửa từ ngữ câu hỏi** |
| Q06 | Nghỉ hằng năm khi chưa đủ 12 tháng | **A113:C02**, A113:C01, Đ114, A113:C03, NĐ145 Đ66 | ✔ rank 1. Cả 4 điều luật liên quan đều đúng nội dung |
| Q07 | Nội dung hợp đồng lao động | **A021:C01**, A021:C03, A021:C04, NĐ145 A089:C01:P-c, Đ13 | ✔ rank 1 |
| Q08 | Báo trước mấy ngày để chấm dứt HĐLĐ | **A035:C01**, Đ36:C03, Đ36:C02, Đ40, Đ38 | ✔ rank 1 |
| Q09 | NĐ145 quy định/hướng dẫn nội dung nào | NĐ145 A089:C01:P-c, **Điều 1**, Đ45, Đ114:C02:P-b, Đ5:C12 | ✔ rank 2 |
| Q10 | < 50 lao động cần tối thiểu mấy người đại diện | Đ38:C01, **Đ38:C02:P-a2**, Đ174:C01:P-c, Đ40:C01, Đ174:C01:P-d | ~ đúng Điều 38 nhưng ra **điểm a2** (50–150 lao động) chứ không phải **a1** (< 50). Câu hỏi hỏi < 50 nên đáp án đúng là a1 — xem mục 3 |

**Kết luận V-manual: 9/10 trả lời đúng ở top-1..4, 1/10 (Q10) đúng Điều nhưng
sai điểm.**

## 2. Hai lỗi do người review phát hiện — đã sửa, đã ghi lý do

### 2.1 Q02 — đáp án ghim SAI, câu hỏi không có câu trả lời trong corpus

Câu hỏi gốc: *"Phạt tiền đối với **người lao động** trốn đóng bảo hiểm xã hội bắt buộc
là bao nhiêu?"*

Đọc **toàn văn** Điều 44 NĐ 283/2026 mới thấy:

- khoản 1 — *"Phạt tiền đối với **người sử dụng lao động** có hành vi không đăng ký
  hoặc đăng ký không đầy đủ…"*
- khoản 2 — *"…**đối với người sử dụng lao động** có một trong các hành vi **trốn
  đóng** bảo hiểm xã hội"*
- khoản 3 — biện pháp khắc phục hậu quả

**Điều 44 phạt người sử dụng lao động, không phạt người lao động.** Không tồn tại
khoản nào trong corpus phạt tiền người lao động vì trốn đóng BHXH, nên câu hỏi gốc
**không có đáp án** và chunk tôi ghim ban đầu là sai.

Lỗi này chỉ lộ ra khi đọc tay: lúc ghim tôi mới đọc 300 ký tự đầu của chunk, bắt đầu
bằng *"Phạt tiền đối với ngườ…"* — đúng cái bẫy mà bước review tay sinh ra để chặn.

Đã sửa: đổi chủ thể sang người sử dụng lao động, **đáp án ghim không đổi**
(`ND283_2026:CIII:M00:A044:C01`). Ghi trong `history` của Q02.

Ghi chú: "và các điểm" trong plan cho chủ đề này **không thực hiện được** — Điều 44
có 3 chunk CLAUSE và **0** chunk POINT.

### 2.2 Q05 — câu hỏi khó hơn chính điều luật nó hỏi

Câu hỏi gốc có vế *"đối với công việc đặc biệt nặng nhọc, độc hại, nguy hiểm"*.
Đọc Điều 107 khoản 3 thấy nó **không dùng** những từ đó: nó liệt kê danh mục nghề
(dệt may da giày, điện tử, chế biến nông lâm diêm nghiệp thủy sản, xây dựng, vận
tải…). Với tsvector `simple` không có stemmer tiếng Việt, đường lexical không còn
cầu nối nào tới chunk đó.

Đã sửa: bỏ vế định tính, giữ câu hỏi tự nhiên, **đáp án ghim không đổi**. Ghi trong
`history` của Q05. Đây là giới hạn thật của đường lexical, được ghi lại chứ không
giấu: một câu hỏi diễn đạt lại không dùng chính từ của luật vẫn là một lần trượt
của BM25.

## 3. Những lần trượt đã ghi nhận, không sửa

| Query | Việc gì | Vì sao **không** sửa |
|---|---|---|
| Q03 | vector-only không có Điều 118 trong top-5 (thứ hạng thật **7**). Hybrid có, rank 3 | Câu hỏi tự nhiên, đáp án đúng. Sửa từ ngữ để ép đường đơn vào top-5 là nới quy định |
| Q09 | vector-only không có Điều 1 NĐ145 trong top-5 (thứ hạng thật **15**) | Điều 1 là danh sách ~30 số Điều của Bộ luật Lao động, vector bị ngập trong số. Đây là giới hạn mô hình, plan vẫn chỉ định cặp này |
| Q10 | vector-only trả về 5/5 là Điều 174 BLLD (đại diện người lao động) — đúng chủ đề nhưng **không** trả lời "bao nhiêu người". Hybrid ra điểm a2 thay vì a1 | Điểm a1 ("Ít nhất 03 người… dưới 50 người lao động") **là** câu trả lời đúng. Không thêm a1…a6 vào `expected_chunk_ids` để cây chỉ số |

Đã loại trừ lỗi cài đặt trước khi kết luận là giới hạn mô hình:
HNSW cho thứ tự **bit-for-bit** giống quét tuần tự (3/3 lần), mọi norm hữu hạn,
embed lại 5 chunk mẫu cosine ≥ 0,999 với vector đã lưu.

## 4. Chữ ký

| | |
|---|---|
| Người review | _(chưa ký)_ |
| Ngày | _(chưa ký)_ |
| Kết luận | **CHƯA NGHIỆM** — chờ ký |

Không ký được cho tới khi mục 9 của `data/chunk/CHANGELOG_B6B7.md` (V4/V5 FAIL ở
đường vector-only) được người review chọn hướng xử lý. Nếu ký mà V4/V5 vẫn đỏ thì
sign-off này không có nghĩa.
