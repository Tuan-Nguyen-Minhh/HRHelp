# Đánh giá định tuyến và trích xuất tình tiết

Kết quả: **Chưa đạt**. Nhãn: **Bản nháp chờ rà soát**.

Định tuyến có cổng Python; trích xuất và hợp nhất tình tiết được đo riêng, với lược đồ đang hoạt động được cung cấp trong đầu vào. Không phải đánh giá hội thoại đầu cuối.

Nhãn nháp chưa được chuyên gia xác nhận. Lỗi API, hết thời gian và phương án dự phòng không được coi là dự đoán đúng hoặc lỗi ngữ nghĩa; các ca này có điểm null.

Tổng số ca: 48; hoàn thành: 46; lỗi xử lý: 2; đạt toàn bộ yêu cầu: 45.

Định tuyến: chấm được 28/30 ca. Tình tiết: chấm được 18/18 ca. Các tỷ lệ bên dưới dùng mẫu số là các ca chấm được.

| Chỉ số | Giá trị |
| --- | --- |
| Định tuyến — độ chính xác nhánh cuối | 1.0000 |
| Định tuyến — tỷ lệ đạt cả nhánh/hành động/hợp đồng | 1.0000 |
| Định tuyến — F1 trung bình giữa các lớp có mẫu | 1.0000 |
| Tình tiết — tỷ lệ ca đạt toàn bộ yêu cầu | 0.9444 |
| Tình tiết sau kiểm tra Python — precision | 1.0000 |
| Tình tiết sau kiểm tra Python — recall | 0.9655 |
| Tình tiết sau kiểm tra Python — F1 | 0.9825 |
| Tình tiết mô hình trước kiểm tra — F1 | 1.0000 |
| Bằng chứng khớp nguyên văn tin nhắn | 1.0000 |
| Thời gian p50 (ms) | 5148 |
| Thời gian p95 (ms) | 8137 |

## Kết quả theo nhánh

| Nhánh | Số mẫu hoàn thành | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| `capability_gap` | 2 | 1.0000 | 1.0000 | 1.0000 |
| `case_qa` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `clarify` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `external_research` | 2 | 1.0000 | 1.0000 | 1.0000 |
| `fact_planner` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `general_chat` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `policy_qa` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `system_help` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `unsupported` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `workflow_action` | 3 | 1.0000 | 1.0000 | 1.0000 |

## Kết quả từng ca

| Ca | Nhóm | Kết quả | Thời gian (ms) |
| --- | --- | --- | --- |
| R01 | Định tuyến | Đạt | 5221 |
| R02 | Định tuyến | Đạt | 5312 |
| R03 | Định tuyến | Đạt | 4202 |
| R04 | Định tuyến | Đạt | 2876 |
| R05 | Định tuyến | Đạt | 5759 |
| R06 | Định tuyến | Đạt | 5695 |
| R07 | Định tuyến | Đạt | 5804 |
| R08 | Định tuyến | Đạt | 6267 |
| R09 | Định tuyến | Đạt | 5845 |
| R10 | Định tuyến | Đạt | 6761 |
| R11 | Định tuyến | Đạt | 6710 |
| R12 | Định tuyến | Đạt | 5997 |
| R13 | Định tuyến | Đạt | 5687 |
| R14 | Định tuyến | Đạt | 3907 |
| R15 | Định tuyến | Đạt | 4465 |
| R16 | Định tuyến | Lỗi xử lý | 8322 |
| R17 | Định tuyến | Đạt | 6193 |
| R18 | Định tuyến | Đạt | 5950 |
| R19 | Định tuyến | Đạt | 5301 |
| R20 | Định tuyến | Lỗi xử lý | 6293 |
| R21 | Định tuyến | Đạt | 4965 |
| R22 | Định tuyến | Đạt | 2331 |
| R23 | Định tuyến | Đạt | 3228 |
| R24 | Định tuyến | Đạt | 3271 |
| R25 | Định tuyến | Đạt | 7434 |
| R26 | Định tuyến | Đạt | 8139 |
| R27 | Định tuyến | Đạt | 5414 |
| R28 | Định tuyến | Đạt | 7523 |
| R29 | Định tuyến | Đạt | 6315 |
| R30 | Định tuyến | Đạt | 5148 |
| F01 | Tình tiết | Chưa đạt | 4698 |
| F02 | Tình tiết | Đạt | 3861 |
| F03 | Tình tiết | Đạt | 7958 |
| F04 | Tình tiết | Đạt | 8148 |
| F05 | Tình tiết | Đạt | 8137 |
| F06 | Tình tiết | Đạt | 3861 |
| F07 | Tình tiết | Đạt | 4952 |
| F08 | Tình tiết | Đạt | 3286 |
| F09 | Tình tiết | Đạt | 4268 |
| F10 | Tình tiết | Đạt | 3402 |
| F11 | Tình tiết | Đạt | 4862 |
| F12 | Tình tiết | Đạt | 3465 |
| F13 | Tình tiết | Đạt | 3529 |
| F14 | Tình tiết | Đạt | 6700 |
| F15 | Tình tiết | Đạt | 3224 |
| F16 | Tình tiết | Đạt | 4151 |
| F17 | Tình tiết | Đạt | 4487 |
| F18 | Tình tiết | Đạt | 4266 |

## Chi tiết chưa đạt

### R16

Gửi hồ sơ này cho pháp chế xem xét.

- Bộ định tuyến dùng phương án dự phòng

- Loại dự phòng: `output`; trạng thái kiểm tra lại: `failed`; nhánh ban đầu: `workflow_action`.

### R20

Ký quyết định kỷ luật thay giám đốc.

- Bộ định tuyến dùng phương án dự phòng

- Loại dự phòng: `output`; trạng thái kiểm tra lại: `failed`; nhánh ban đầu: `unsupported`.

### F01

- Diễn biến sự việc: Nhân viên tự ý nghỉ 5 ngày làm việc không phép.
• Không gửi đơn xin nghỉ hoặc thông báo cho quản lý trước khi vắng mặt.

- Thiếu, sai giá trị hoặc thêm tình tiết ngoài nhãn.
- Danh sách tình tiết còn thiếu không đúng.
- Sau kiểm tra Python: thiếu/sai ['notice_form']; thừa/sai [].
- Đầu ra mô hình: thiếu/sai []; thừa/sai [].
- Tình tiết thực tế: `{"absence_days": {"value": "5 ngày", "confirmed": true}}`.
- Tình tiết đúng ở đầu ra mô hình nhưng bị mất sau kiểm tra Python: ['notice_form'].

## Phạm vi và giới hạn

- Ca định tuyến dùng mô hình thật, bước kiểm tra lại ngữ nghĩa và cổng Python của ứng dụng; quy tắc từ khóa không được dùng làm đáp án thay thế.
- Ca tình tiết gọi trực tiếp thành phần trích xuất với lược đồ đang hoạt động; chưa đo xác suất định tuyến đúng rồi mới trích xuất đúng trong một hội thoại hoàn chỉnh.
- Các phép so giá trị dùng nhãn độc lập và các biến thể được chấp nhận; không dùng hàm chuẩn hóa của ứng dụng để tự chấm ứng dụng.
- Trích dẫn nguyên văn là kiểm tra cơ học, không tự xác nhận quan hệ suy luận. Nhãn contains_all cho mô tả chỉ kiểm tra các cụm đã khai báo.
- Bộ nhỏ, hiển thị công khai, pha trộn ca tổng hợp và trích đoạn nguồn; không phải ước lượng không thiên lệch về dữ liệu vận hành.
- Không đo truy xuất, nội dung trả lời, thao tác cơ sở dữ liệu, phê duyệt hoặc độ đúng pháp lý.
