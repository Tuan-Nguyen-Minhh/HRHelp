# Kết quả đánh giá hồ sơ bằng RAGAS

Trạng thái: complete. Số mẫu: 5.

Phạm vi: live_retrieval_direct_component; not end-to-end chat.
Đáp án tham chiếu là bản nháp chưa được chuyên gia xác nhận.

| Chỉ số | Trung bình | Mẫu có điểm |
| --- | --- | --- |
| faithfulness | 0.8245 | 5/5 |
| factual_correctness | 0.5760 | 5/5 |
| context_precision | 0.9141 | 5/5 |
| context_recall | 0.3496 | 5/5 |

Faithfulness mặc định kiểm tra cả tình tiết đầu vào và chứng cứ chính sách.
Chỉ số truy xuất, nếu được chọn, chỉ dùng chứng cứ chính sách làm tham chiếu; không dùng tình tiết nhân viên.
Điểm còn thiếu được ghi null, không chuyển thành 0 hoặc coi là thành công.
Nếu dùng chứng cứ cố định, điểm không đo chất lượng bộ truy xuất trực tiếp.
