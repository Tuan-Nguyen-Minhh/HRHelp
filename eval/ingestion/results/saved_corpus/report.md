# Đánh giá kho tri thức và quy trình nạp dữ liệu

Kết quả: **Chưa đạt**. Trạng thái nhãn: **Bản nháp chờ rà soát**.

Đối chiếu nội dung, siêu dữ liệu, ngữ cảnh và dẫn chiếu với nguồn trên các tệp chunk; chưa kiểm tra cơ sở dữ liệu đang chạy hoặc vector.

Phạm vi thu thập đầu ra: Các tệp chunk đã lưu; chưa chạy lại các bước xử lý trước đó.

Nhãn nháp chưa đủ để xác nhận độ chính xác của kho tri thức đã được chuyên gia kiểm chứng.

| Chỉ số | Giá trị |
| --- | --- |
| Tổng số đoạn nguồn được gán nhãn (`source_spans_total`) | 189 |
| Số đoạn nguồn được bảo toàn (`source_spans_preserved`) | 187 |
| Tỷ lệ bảo toàn đoạn nguồn (`span_preservation_rate`) | 0.9894 |
| Tỷ lệ đoạn nguồn có đầy đủ nội dung trong phần truy xuất có thể đọc (`retrieval_visible_span_rate`) | 0.9841 |
| Số đoạn được bảo toàn có siêu dữ liệu đúng (`preserved_spans_with_correct_metadata`) | 187 |
| Tỷ lệ siêu dữ liệu đạt trên các đoạn được bảo toàn (`metadata_pass_rate_on_preserved_spans`) | 1.0000 |
| Tỷ lệ ngữ cảnh đạt trên các đoạn được bảo toàn (`context_pass_rate_on_preserved_spans`) | 0.9947 |
| Số dẫn chiếu mong đợi cần tìm (`expected_positive_references`) | 5 |
| Tỷ lệ tìm được các dẫn chiếu mong đợi (`positive_reference_recall`) | 0.6000 |
| Số ca đạt (`cases_passed`) | 14 |
| Tổng số ca (`cases_total`) | 16 |
| Số chunk có nội dung chính phát sinh hoặc bị sửa ngoài nguồn (`chunks_with_unexpected_body_text`) | 0 |

## Đối chiếu nguồn

Mã băm các tệp nguồn gốc khớp với giá trị đã cố định.

## Danh mục văn bản

| Văn bản | Số chunk | Số điều xuất hiện / mong đợi | Kết quả |
| --- | --- | --- | --- |
| BLLD | 381 | 220/220 | Đạt |
| ND145_2020 | 377 | 115/115 | Đạt |
| ND283_2026 | 531 | 68/68 | Đạt |
| NQCT | 116 | 82/82 | Đạt |

## Kết quả từng ca

| Ca đánh giá | Số đoạn nguồn được bảo toàn | Kết quả |
| --- | --- | --- |
| BLLD-A001 | 1/1 | Đạt |
| BLLD-A012 | 3/3 | Đạt |
| BLLD-A118 | 14/14 | Đạt |
| BLLD-A125 | 6/6 | Đạt |
| ND145_2020-A003 | 4/4 | Đạt |
| ND145_2020-A069 | 13/14 | Chưa đạt |
| ND145_2020-A070 | 7/8 | Chưa đạt |
| ND145_2020-A084 | 6/6 | Đạt |
| ND283_2026-A001 | 5/5 | Đạt |
| ND283_2026-A002 | 3/3 | Đạt |
| ND283_2026-A049 | 76/76 | Đạt |
| ND283_2026-A050 | 32/32 | Đạt |
| NQCT-A004 | 6/6 | Đạt |
| NQCT-A008 | 2/2 | Đạt |
| NQCT-A010 | 5/5 | Đạt |
| NQCT-A013 | 4/4 | Đạt |

## Chi tiết chưa đạt

### NQCT

- Nhãn điều không có trong danh mục nguồn: 100, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99.

### ND145_2020-A069

- Đoạn nguồn bị thiếu hoặc thay đổi tại vị trí 660: 2.Nội dung nội quy lao động không được trái với pháp luật về lao động và quy định của pháp luật có liên quan. Nội quy lao động gồm những nội dung chủ yếu sau:
- Thiếu dẫn chiếu: văn bản 18/VBHN-VPQH, Điều 118.

### ND145_2020-A070

- ND145_2020:CVIII:M00:A070:C01: Nội dung nguồn chỉ còn trong siêu dữ liệu, không có trong nội dung chính hoặc tiêu đề ngữ cảnh.
- Đoạn nguồn bị thiếu hoặc thay đổi tại vị trí 675: 2. Trong thời hiệu xử lý kỷ luật lao động quy định tại khoản 1, khoản 2 Điều 123 của Bộ luật Lao động, người sử dụng lao động tiến hành họp xử lý kỷ luật lao động như sau:
- Thiếu dẫn chiếu: văn bản 18/VBHN-VPQH, Điều 122, khoản 6.

## Chưa được đánh giá

- Tính đúng đắn pháp lý, tính chính thống của nguồn và ngày hiệu lực.
- Độ chính xác dẫn chiếu trên toàn kho.
- Độ chính xác nội dung các điều chưa được gán nhãn.
- Độ khớp dữ liệu lưu trong cơ sở dữ liệu đang chạy và tính toàn vẹn của vector.
- Khả năng sử dụng ngữ nghĩa của chunk ngoài những yêu cầu ngữ cảnh cụ thể đã định nghĩa.
- Mức đầy đủ của bảng, hình ảnh và phụ lục.
- Nội dung được thêm vào tiêu đề hoặc siêu dữ liệu không có căn cứ, và nội dung các điều chưa được gán nhãn.
