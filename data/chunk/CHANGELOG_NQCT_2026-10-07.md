# CHANGELOG — Mở rộng NQCT (nội quy lao động): 82 → 100 Điều từ nội quy công ty thực tế

_Ngày: 2026-10-07. Nhánh `tuan_data_pipeline`. Phạm vi: chỉ văn bản nội bộ `NQCT` (`NQLD-HRCORP-2026`) + hạ tầng đếm số. Ba văn bản luật (BLLD `18/VBHN-VPQH`, NĐ 145/2020, NĐ 283/2026) **không đổi byte nào**._

## 1. Mục tiêu & Nguồn dữ liệu

- **Mục tiêu:** Mở rộng văn bản nội bộ NQCT từ 82 lên 100 Điều bằng các họ quy trình vận hành thực tế đã kiểm chuẩn, đưa qua đầy đủ pipeline `step3 → seed_legal → embed_legal → seed_hr_from_legal → copy_chunk_references`.
- **Nguồn:** `data/raw/noi_quy_lao_dong_2026.docx` (Nội quy lao động của công ty sản xuất - xây dựng thực tế, 12 Chương, 68 Điều).
- **Chuyển đổi tham chiếu:** Chuyển sang `data/reference/noi_quy_lao_dong_2026.md` bằng MarkItDown.

## 2. Gap Analysis & Các họ quy trình đã thêm (Chương XXII–XXX, Điều 83–100, +18 Điều)

| Chương | Điều | Họ quy trình | Gốc & Pháp lý |
| --- | --- | --- | --- |
| XXII | 83–84 | Quản lý con dấu (4 bước, két sắt, cấm đóng khống chỉ, mang ra ngoài) & Quản lý chữ ký số / Token USB (cấp phát, bảo mật PIN, thu hồi trong 24h) | Điều 24, 26 nguồn |
| XXIII | 85–87 | Kiểm soát người & phương tiện ra vào cổng (tốc độ ≤10km/h, kiểm tra thùng xe), Tiếp đón khách (Visitor Card, cấm vào khu sản xuất/server khi chưa duyệt), Mang tài sản ra ngoài (Phiếu ra cổng, đối chiếu serial) | Điều 14, 24 nguồn |
| XXIV | 88–89 | Quản lý & cấp phát PPE miễn phí, nguyên tắc "đổi cũ lấy mới" khi hư hỏng, kiểm tra PPE đầu ca & thu hồi khi thôi việc | Điều 17 nguồn + Luật ATVSLĐ |
| XXV | 90–91 | Tạm thời điều chuyển NLĐ làm công việc khác: căn cứ thiên tai/dịch bệnh/sự cố/SXKD cấp bách, báo trước 03 ngày làm việc, tối đa 60 ngày/năm, bảo lưu lương cũ 30 ngày nếu lương mới thấp hơn, lương mới ≥ 85% lương cũ | Điều 18 nguồn + BLLD Điều 29 |
| XXVI | 92–93 | Tiếp nhận đơn tố cáo quấy rối tình dục (kênh bảo mật, cách ly bảo vệ nạn nhân) & Trình tự xác minh (Tổ xác minh 3 người, thời hạn 15–30 ngày làm việc, đối chất kín, xử lý kỷ luật hoặc xử lý vu khống) | Điều 19, 20, 23 nguồn + NĐ 145 Điều 84, 85, 86 |
| XXVII | 94–95 | Giải quyết chế độ BHXH ốm đau, thai sản: nộp hồ sơ (Mẫu C65-HD, giấy ra viện, khai sinh) trong 45 ngày; Nhân sự nộp Mẫu 01B-HSB trong 10 ngày; chi trả trực tiếp và chính sách tạm ứng viện phí tối đa 50% lương | Điều 9, 10, 12, 13 nguồn + Luật BHXH |
| XXVIII | 96–97 | Ứng phó sự cố y tế (Tủ thuốc, sơ cấp cứu, chuyển viện 115) & Kiểm soát dịch bệnh truyền nhiễm (Ban chỉ đạo, đo thân nhiệt, khử khuẩn, cách ly tạm thời, làm việc từ xa) | Điều 14, 15, 16 nguồn |
| XXIX | 98–99 | Tự động xóa kỷ luật (3 tháng với khiển trách, 6 tháng với kéo dài nâng lương, 3 năm với cách chức) & Quy trình xét giảm thời hạn chấp hành kỷ luật khi đã chấp hành 1/2 thời hạn | Điều 38 nguồn + BLLD Điều 126 |
| XXX | 100 | Điều khoản thi hành và tổ chức thực hiện 100 Điều Nội quy lao động | Điều khoản kết |

## 3. Rà soát pháp lý & Tuân thủ Điều 124 BLLD

- **Loại bỏ triệt để mọi hình thức trái luật:** Không có "phạt tiền", "trừ lương", "bản kiểm điểm". Toàn bộ hình thức xử lý vi phạm bám sát 4 hình thức luật định theo Điều 124 BLLD (Khiển trách, Kéo dài thời hạn nâng lương không quá 06 tháng, Cách chức, Sa thải).
- **Trích dẫn luật chuẩn xác:**
  + Điều 29 BLLD (Chuyển người lao động làm công việc khác so với HĐLĐ).
  + Điều 124 BLLD (Hình thức xử lý kỷ luật lao động).
  + Điều 125 BLLD (Sa thải).
  + Điều 126 BLLD (Xóa kỷ luật, giảm thời hạn chấp hành kỷ luật).
  + Điều 84, 85, 86 Nghị định 145/2020/NĐ-CP (Phòng chống quấy rối tình dục tại nơi làm việc).
  + Dẫn chiếu nội bộ (`scope.document_id = "NQLD-HRCORP-2026"`): nhận diện cả "Nội quy này" và "Nội quy lao động này".

## 4. Kết quả Pipeline & Đối chiếu dữ liệu

| Chỉ số | Trước (82 Điều) | Sau (100 Điều) | Chênh lệch |
| --- | --- | --- | --- |
| NQCT Điều | 82 | **100** | +18 Điều |
| NQCT chunk | 88 | **116** (90 ARTICLE + 26 CLAUSE) | +28 chunk |
| NQCT cross-ref | 33 | **50** (toàn bộ HIGH) | +17 ref |
| Tổng chunk corpus | 1377 | **1405** (381 BLLD + 377 ND145 + 531 ND283 + 116 NQCT) | +28 chunk |
| Tổng ref corpus | 599 | **615** (612 HIGH, 3 LOW BOUNDARY hợp lệ) | +16 ref |
| Vector embeddings | 1377 | **1405** (1024-dim mistral-embed, 0 null) | +28 vectors |
| UNRESOLVED refs | 0 | **0** | 0 |
| Chunk over 1000 tokens | 0 | **0** (NQCT: 0 over-limit) | 0 |
| Pytest test suite | 178 passed | **178 passed** | 100% PASS |

## 5. Golden Set & Retrieval Evaluation

Đã chạy probe retrieval trên các chủ đề mới và pin 3 query chuẩn vào `eval/legal_golden.json`:
- **Q16**: "Thủ tục mang con dấu công ty ra ngoài trụ sở cần ai phê duyệt?" → `NQCT:CXXII:M00:A083:C03` (Top-1 Vector sim=0.8523, Top-1 BM25).
- **Q17**: "Quy trình đổi mới phương tiện bảo vệ cá nhân theo nguyên tắc nào?" → `NQCT:CXXIV:M00:A088:C02` (Top-1 Vector sim=0.8605, Top-1 BM25).
- **Q18**: "Tổ xác minh khiếu nại quấy rối tình dục gồm bao nhiêu thành viên và thời hạn xác minh?" → `NQCT:CXXVI:M00:A093:C01` (Top-1 Vector sim=0.8432, Top-1 BM25).
