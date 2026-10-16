# Đánh giá chất lượng truy xuất

Trạng thái nhãn: **Bản nháp chờ chuyên gia rà soát**.

20 ca truy xuất; nhãn chứng cứ tối thiểu và mức liên quan là bản nháp. Không xác nhận căn cứ đủ để ra quyết định pháp lý.

Đã chạy 20/20 ca; lỗi xử lý: 0; đầu ra suy giảm: 0; đạt đủ phép kiểm tra đã gán nhãn: 20.

Cảnh báo gói chứng cứ (số ca): `EVIDENCE_BUDGET_EXCEEDED`: 17, `MISSING_AUTHORITY`: 1, `MISSING_INTERNAL_RULE`: 1. Các cảnh báo này được báo riêng, không bị xóa bởi kết quả đạt bộ nhãn tối thiểu.

Nhãn chưa bao phủ hết đoạn liên quan. Precision/nDCG cận dưới coi đoạn chưa gán nhãn là 0 để chẩn đoán, không chứng minh chúng không liên quan. Precision trên nhãn phải đọc cùng tỷ lệ đầu ra đã có nhãn.

Số cạnh dẫn chiếu trong DB được chụp: **0**. Không đủ dữ liệu để đo lợi ích mở rộng đồ thị.

Corpus giữ nguyên sau lần chạy: **Có**.

Khoảng cách tối thiểu giữa các request rerank: 7.0 giây. Thời gian đo bao gồm chờ điều tiết API; không dùng làm độ trễ phục vụ người dùng.

| Chỉ số | Trung bình | Số ca có điểm |
| --- | --- | --- |
| Recall tập ứng viên (`candidate_recall`) | 1.0000 | 19 |
| Recall gói chứng cứ cuối (`final_recall`) | 1.0000 | 19 |
| Tỷ lệ giữ đủ một bộ chứng cứ tối thiểu đã gán nhãn (`complete_labeled_bundle`) | 1.0000 | 19 |
| Recall chunk quan trọng (`critical_chunk_recall`) | 1.0000 | 18 |
| Precision cận dưới theo nhãn hiện có (`labeled_precision_lower_bound`) | 0.2588 | 19 |
| Precision chỉ trên các đoạn đã gán nhãn (`judged_precision`) | 1.0000 | 19 |
| Tỷ lệ đầu ra đã có nhãn (`judgment_coverage`) | 0.2588 | 19 |
| nDCG cận dưới theo nhãn hiện có (`ndcg_lower_bound`) | 0.8660 | 19 |
| Tỷ lệ đúng bộ lọc phiên bản/ngày (`date_eligibility_pass`) | 1.0000 | 20 |
| Tỷ lệ giữ nguyên toàn bộ nội dung các chunk được chọn (`passage_fidelity_pass`) | 1.0000 | 20 |
| Tỷ lệ ca không có corpus đủ điều kiện trả về rỗng (`expected_empty_pass`) | 1.0000 | 1 |
| Mức tăng recall từ các ứng viên có nguồn đồ thị (`graph_recall_gain`) | Chưa có điểm | 0 |
| Thời gian trung bình (ms) (`latency_ms`) | 33542.0500 | 20 |
| Số đoạn cuối trung bình (`selected_count`) | 11.4000 | 20 |

## Recall theo giai đoạn

| Giai đoạn | Recall trung bình | Số ca có điểm |
| --- | --- | --- |
| Ứng viên vector | 0.6272 | 19 |
| Ứng viên BM25 | 0.9035 | 19 |
| Ứng viên từ khóa | 0.7719 | 19 |
| Pool RRF | 1.0000 | 19 |
| Hạt giống top-5 cho đồ thị (không thay pool RRF) | 0.8772 | 19 |
| Pool mở rộng và tìm bổ sung nếu có | 1.0000 | 19 |

## Kết quả từng ca

| Ca | Recall ứng viên | Recall cuối | Đủ bộ nhãn | Recall quan trọng | Hệ thống khỏe |
| --- | --- | --- | --- | --- | --- |
| S01 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| S02 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| S03 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| S04 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| S05 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q06 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q07 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q08 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q09 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q10 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q11 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q12 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q13 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q14 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q15 | 1.0000 | 1.0000 | Có | Chưa có điểm | Có |
| Q16 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q17 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q18 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q19 | 1.0000 | 1.0000 | Có | 1.0000 | Có |
| Q20 | Chưa có điểm | Chưa có điểm | Chưa có điểm | Chưa có điểm | Có |

## Chi tiết chứng cứ và lỗi

### S01

- Diễn biến sự việc: Nhân viên tự ý nghỉ 5 ngày làm việc không phép.
Tìm căn cứ nội quy và pháp luật, kèm điều kiện cần kiểm tra trước khi đề xuất xử lý.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 7.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 13/-/- | 3 | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| NQCT | 4/-/- | Chưa gán nhãn | `0812add5-c466-47fc-87cf-2c085cda1b87` |
| BLLD_2019 | 125/-/- | 3 | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 115/-/- | Chưa gán nhãn | `1b730e11-d067-4b4a-acb2-51e0d7209b30` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| BLLD_2019 | 122/1/- | 1 | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| NQCT | 11/-/- | Chưa gán nhãn | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| BLLD_2019 | 122/4/- | Chưa gán nhãn | `e1ae17b1-b450-4e2a-8803-ceecc6b84c50` |
| NQCT | 15/-/- | 1 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 14/-/- | 1 | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |

### S02

- Diễn biến sự việc: Nhân viên đi làm muộn 4 lần trong tháng.
Tìm căn cứ nội quy và pháp luật, kèm điều kiện cần kiểm tra trước khi đề xuất xử lý.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 8.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 11/-/- | 3 | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| BLLD_2019 | 118/-/- | 3 | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 119/-/- | Chưa gán nhãn | `30981c98-6047-4c6d-a6da-9a229ebcbc5e` |
| NQCT | 3/-/- | Chưa gán nhãn | `dbbb3ca2-4003-408b-a50f-6a85e737cd5a` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 14/-/- | 1 | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 15/-/- | 1 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 2/-/- | Chưa gán nhãn | `cf5db6c1-2585-4fbb-ad32-51b6be2be3ef` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |

### S03

- Diễn biến sự việc: Nhân viên nộp báo cáo công việc trễ hạn.
Tìm căn cứ nội quy và pháp luật, kèm điều kiện cần kiểm tra trước khi đề xuất xử lý.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 7.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 11/-/- | 3 | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| BLLD_2019 | 122/1/- | 1 | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| BLLD_2019 | 118/-/- | 3 | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 14/-/- | 1 | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 15/-/- | 1 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 2/-/- | Chưa gán nhãn | `cf5db6c1-2585-4fbb-ad32-51b6be2be3ef` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| NQCT | 1/-/- | Chưa gán nhãn | `ca7b6f9b-119b-4f03-b669-e14c59456564` |

### S04

- Diễn biến sự việc: Nhân viên rời vị trí làm việc khi chưa bàn giao.
Tìm căn cứ nội quy và pháp luật, kèm điều kiện cần kiểm tra trước khi đề xuất xử lý.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 7.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| NQCT | 11/-/- | 3 | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| BLLD_2019 | 40/-/- | Chưa gán nhãn | `68488e14-8044-42a9-9c75-e64fde741b08` |
| BLLD_2019 | 122/1/- | 1 | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| NQCT | 14/-/- | 1 | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 15/-/- | 1 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| BLLD_2019 | 118/-/- | 3 | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 35/1/- | Chưa gán nhãn | `986582ca-db07-49b7-ae28-52118c5f4075` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |

### S05

- Diễn biến sự việc: Nhân viên không sử dụng đầy đủ trang bị bảo hộ theo quy trình.
Tìm căn cứ nội quy và pháp luật, kèm điều kiện cần kiểm tra trước khi đề xuất xử lý.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 7.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 7/-/- | 3 | `5a647271-68ce-453f-bd35-a862e4d14d08` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| BLLD_2019 | 134/-/- | Chưa gán nhãn | `cd3fcc2e-b5e7-4696-84c6-4eebd7b20999` |
| BLLD_2019 | 118/-/- | 3 | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 122/1/- | 1 | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| NQCT | 14/-/- | 1 | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 15/-/- | 1 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| BLLD_2019 | 122/2/- | Chưa gán nhãn | `b3be50af-b6f2-498f-9f52-4723ed04b973` |
| NQCT | 2/-/- | Chưa gán nhãn | `cf5db6c1-2585-4fbb-ad32-51b6be2be3ef` |
| NQCT | 1/-/- | Chưa gán nhãn | `ca7b6f9b-119b-4f03-b669-e14c59456564` |

### Q06

Nhân viên tự ý nghỉ 3 ngày trong 30 ngày. Tìm điều kiện theo nội quy, cách báo vắng và nền tảng pháp luật.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 9.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 4/-/- | 3 | `0812add5-c466-47fc-87cf-2c085cda1b87` |
| NQCT | 12/-/- | 3 | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| BLLD_2019 | 125/-/- | Chưa gán nhãn | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 115/-/- | Chưa gán nhãn | `1b730e11-d067-4b4a-acb2-51e0d7209b30` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| NQCT | 11/-/- | Chưa gán nhãn | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| BLLD_2019 | 118/-/- | 3 | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 36/1/e | Chưa gán nhãn | `e08afa41-2e8f-4bd4-aac2-a3ab53b6087a` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| BLLD_2019 | 122/4/- | Chưa gán nhãn | `e1ae17b1-b450-4e2a-8803-ceecc6b84c50` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |

### Q07

Nghỉ 5 ngày trong 30 ngày vì bản thân bị ốm có giấy xác nhận. Cần kiểm tra ngoại lệ lý do chính đáng trong nội quy và Bộ luật Lao động.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 13/-/- | 3 | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| NQCT | 4/-/- | Chưa gán nhãn | `0812add5-c466-47fc-87cf-2c085cda1b87` |
| BLLD_2019 | 125/-/- | 3 | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 122/4/- | Chưa gán nhãn | `e1ae17b1-b450-4e2a-8803-ceecc6b84c50` |
| BLLD_2019 | 115/-/- | Chưa gán nhãn | `1b730e11-d067-4b4a-acb2-51e0d7209b30` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 141/-/- | Chưa gán nhãn | `c564139d-0e49-4731-a477-fe26195f30e3` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| BLLD_2019 | 37/-/- | Chưa gán nhãn | `ab26b6e8-2b62-426a-b3eb-e8b665460284` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |

### Q08

Nhân viên chuyển dữ liệu khách hàng cho bên thứ ba khi không có nhiệm vụ. Tìm quy định về bí mật và điều kiện xử lý.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 9.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 6/-/- | 3 | `3791d3ec-e215-419a-b3ef-7f2386456154` |
| NQCT | 13/-/- | 3 | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| BLLD_2019 | 21/2/- | Chưa gán nhãn | `5c2a053b-75ef-4be0-9439-e4cf0a91bf3a` |
| BLLD_2019 | 125/-/- | 3 | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 1/-/- | Chưa gán nhãn | `ca7b6f9b-119b-4f03-b669-e14c59456564` |
| NQCT | 2/-/- | Chưa gán nhãn | `cf5db6c1-2585-4fbb-ad32-51b6be2be3ef` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| BLLD_2019 | 5/2/- | Chưa gán nhãn | `a4262ce5-00ee-4518-a44f-358a5e65694b` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |

### Q09

Hành vi quấy rối tình dục xảy ra trong chuyến công tác. Tìm định nghĩa, phạm vi nơi làm việc, nội quy và điều kiện áp dụng.

Ngày dùng để lọc: 2026-08-15.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 8.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 8/-/- | 3 | `902fac74-b956-4ada-b126-72763228309e` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| ND145_2020 | 84/3/- | 3 | `7a66c7c2-8580-48da-a43c-894a7eeb87f5` |
| BLLD_2019 | 3/9/- | Chưa gán nhãn | `1fb462ef-af13-4556-b3c5-6f2f66089d0f` |
| ND145_2020 | 85/-/- | Chưa gán nhãn | `66489ac0-ac52-4359-8064-e1b0ba527fbf` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| ND145_2020 | 84/2/- | Chưa gán nhãn | `90133201-5ce7-4d07-87aa-753d96c0daa0` |
| ND145_2020 | 84/1/- | 3 | `8b2e283e-734d-4d6a-ad12-3bdd053ac719` |
| ND145_2020 | 69/2/d | Chưa gán nhãn | `e6acb658-4be2-4383-801b-4935604b94f4` |
| BLLD_2019 | 125/-/- | 3 | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| ND145_2020 | 86/1/- | Chưa gán nhãn | `ce799348-1160-4509-9b74-390bcb04117d` |
| BLLD_2019 | 8/-/- | Chưa gán nhãn | `8f8c5cca-726d-4f0a-989e-cd25a145110d` |

### Q10

Cần kiểm tra trường hợp chưa được xử lý kỷ luật: người lao động đang mang thai hoặc mất khả năng nhận thức do bệnh.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| BLLD_2019 | 122/4/- | 3 | `e1ae17b1-b450-4e2a-8803-ceecc6b84c50` |
| BLLD_2019 | 122/5/- | 3 | `ec55a44e-bc3a-4046-82bd-db5b7df46165` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| BLLD_2019 | 125/-/- | Chưa gán nhãn | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| BLLD_2019 | 137/3/- | Chưa gán nhãn | `81817aeb-f763-4a3a-a737-ed0ae4d31aa7` |

### Q11

Có được phạt tiền hoặc cắt lương thay cho xử lý kỷ luật lao động không? Tìm điều cấm trong luật và nội quy.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: [].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 10/-/- | 3 | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| BLLD_2019 | 127/-/- | 3 | `b43ce99b-50d8-4f7c-860e-75c3a25bba6b` |
| BLLD_2019 | 129/-/- | Chưa gán nhãn | `74f24434-cad1-481d-b3d0-9b1a4495cc42` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 11/-/- | Chưa gán nhãn | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| NQCT | 2/-/- | Chưa gán nhãn | `cf5db6c1-2585-4fbb-ad32-51b6be2be3ef` |
| NQCT | 17/-/- | Chưa gán nhãn | `ec184d4a-841f-4ff1-b596-fcc91f03711e` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |

### Q12

Tìm thời hiệu xử lý kỷ luật thông thường và trường hợp liên quan tài chính, tài sản, bí mật kinh doanh theo luật và nội quy.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 18/-/- | 3 | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| BLLD_2019 | 123/-/- | 3 | `0625a584-8e80-4cfa-83a0-c058c9471096` |
| BLLD_2019 | 125/-/- | Chưa gán nhãn | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 122/6/- | Chưa gán nhãn | `b28f0706-d2fc-490d-83db-a39a44571355` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| BLLD_2019 | 117/-/- | Chưa gán nhãn | `e1b907a2-ba21-4c04-89dc-b8289c15fbbb` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 6/-/- | Chưa gán nhãn | `3791d3ec-e215-419a-b3ef-7f2386456154` |

### Q13

Nhân viên đã bị kéo dài thời hạn nâng lương, nay lặp lại hành vi. Tìm điều kiện tái phạm và xóa kỷ luật trước khi đề xuất.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 9.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 13/-/- | 3 | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| BLLD_2019 | 125/-/- | 3 | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 126/-/- | 3 | `d2c381cd-ff74-466c-9a9e-160d05daf794` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| BLLD_2019 | 124/-/- | Chưa gán nhãn | `4209ec08-1cfe-42db-bc10-4abdbdd82cdc` |
| BLLD_2019 | 123/-/- | Chưa gán nhãn | `0625a584-8e80-4cfa-83a0-c058c9471096` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 11/-/- | Chưa gán nhãn | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |

### Q14

Liệt kê các hình thức xử lý kỷ luật được quy định trong Bộ luật Lao động và nội quy công ty.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 10/-/- | 3 | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| BLLD_2019 | 124/-/- | 3 | `4209ec08-1cfe-42db-bc10-4abdbdd82cdc` |
| BLLD_2019 | 125/-/- | Chưa gán nhãn | `52e33d20-472b-45a9-97bd-3f0bc2d2d6de` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| NQCT | 11/-/- | Chưa gán nhãn | `55788187-2ee7-4b3d-a89d-a1a46b14e3d6` |
| BLLD_2019 | 122/4/- | Chưa gán nhãn | `e1ae17b1-b450-4e2a-8803-ceecc6b84c50` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| BLLD_2019 | 122/5/- | Chưa gán nhãn | `ec55a44e-bc3a-4046-82bd-db5b7df46165` |
| BLLD_2019 | 122/6/- | Chưa gán nhãn | `b28f0706-d2fc-490d-83db-a39a44571355` |
| BLLD_2019 | 127/-/- | Chưa gán nhãn | `b43ce99b-50d8-4f7c-860e-75c3a25bba6b` |

### Q15

Tìm quy định có nêu thời hạn thông báo trước cuộc họp xử lý kỷ luật lao động.

Ngày dùng để lọc: 2026-09-09.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 15/-/- | 3 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| ND145_2020 | 70/2/a | 3 | `8526e91e-6e31-4edc-993f-b3b9a1a65272` |
| ND145_2020 | 70/2/c | Chưa gán nhãn | `4db67952-5cd7-4998-a53b-8c23b3a993be` |
| BLLD_2019 | 123/-/- | Chưa gán nhãn | `0625a584-8e80-4cfa-83a0-c058c9471096` |
| ND145_2020 | 70/2/b | Chưa gán nhãn | `4c7cedf6-e073-4852-801f-279f298e226f` |
| ND145_2020 | 71/2/a | Chưa gán nhãn | `c675c268-2bae-4df8-b2fb-6a26d935035a` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| ND145_2020 | 70/3/- | Chưa gán nhãn | `a7fdcfe6-d654-4904-9ed9-f50e3da21ee5` |
| BLLD_2019 | 122/4/- | Chưa gán nhãn | `e1ae17b1-b450-4e2a-8803-ceecc6b84c50` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| ND145_2020 | 71/2/b | Chưa gán nhãn | `8e2037d7-d155-4b72-bff7-3fcd56857b21` |

### Q16

Khi phát hiện vi phạm và tổ chức họp kỷ luật, việc lập biên bản và chữ ký của người tham dự được quy định ra sao?

Ngày dùng để lọc: 2026-08-15.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: [].
- Số đoạn chưa gán nhãn: 8.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 14/-/- | 3 | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| ND145_2020 | 70/3/- | 3 | `a7fdcfe6-d654-4904-9ed9-f50e3da21ee5` |
| ND145_2020 | 70/1/- | 3 | `a8435b93-3eae-444f-af6e-6ecf357496d8` |
| BLLD_2019 | 122/1/- | 1 | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| ND145_2020 | 70/2/b | Chưa gán nhãn | `4c7cedf6-e073-4852-801f-279f298e226f` |
| ND145_2020 | 70/2/c | Chưa gán nhãn | `4db67952-5cd7-4998-a53b-8c23b3a993be` |
| ND145_2020 | 71/3/- | Chưa gán nhãn | `d233931c-ecbe-4d91-ab68-b4588fe83e3d` |
| ND145_2020 | 70/2/a | Chưa gán nhãn | `8526e91e-6e31-4edc-993f-b3b9a1a65272` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| BLLD_2019 | 122/3/- | Chưa gán nhãn | `bfd3b222-123d-4f1a-bb41-391cf9239745` |

### Q17

Ai có thẩm quyền xử lý và ký quyết định kỷ luật lao động theo nội quy và văn bản hướng dẫn?

Ngày dùng để lọc: 2026-08-15.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 10.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 16/-/- | 3 | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 1/-/- | Chưa gán nhãn | `ca7b6f9b-119b-4f03-b669-e14c59456564` |
| ND145_2020 | 69/2/i | 3 | `056e648c-af93-4d58-bee6-3edf518f5a09` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| ND145_2020 | 70/4/- | Chưa gán nhãn | `9e1e504c-d536-45ad-bd5b-f837ebe0dcfa` |
| ND145_2020 | 70/2/c | Chưa gán nhãn | `4db67952-5cd7-4998-a53b-8c23b3a993be` |
| BLLD_2019 | 122/6/- | Chưa gán nhãn | `b28f0706-d2fc-490d-83db-a39a44571355` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| BLLD_2019 | 117/-/- | Chưa gán nhãn | `e1b907a2-ba21-4c04-89dc-b8289c15fbbb` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |

### Q18

Người lao động sơ suất làm hỏng dụng cụ, thiệt hại không nghiêm trọng. Tìm trách nhiệm vật chất, mức bồi thường và nguyên tắc xem xét.

Ngày dùng để lọc: 2026-10-16.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 9.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 17/-/- | 3 | `ec184d4a-841f-4ff1-b596-fcc91f03711e` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| BLLD_2019 | 129/-/- | 3 | `74f24434-cad1-481d-b3d0-9b1a4495cc42` |
| BLLD_2019 | 130/-/- | 3 | `bcc64089-9d9e-4951-b3c8-f748c462a018` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| BLLD_2019 | 122/6/- | Chưa gán nhãn | `b28f0706-d2fc-490d-83db-a39a44571355` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| BLLD_2019 | 102/-/- | Chưa gán nhãn | `74c17390-69b8-43d8-8598-7b69385ed211` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 15/-/- | Chưa gán nhãn | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| BLLD_2019 | 131/-/- | Chưa gán nhãn | `8d640dec-b1bc-4119-8baa-3f24cd795afb` |

### Q19

Tìm quy định có nêu thời hạn thông báo trước cuộc họp xử lý kỷ luật lao động.

Ngày dùng để lọc: 2026-09-10.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['EVIDENCE_BUDGET_EXCEEDED'].
- Số đoạn chưa gán nhãn: 11.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |
| NQCT | 15/-/- | 3 | `779013cd-822a-4a5d-9bbc-4d5294019406` |
| NQCT | 18/-/- | Chưa gán nhãn | `452b101e-b011-4b2b-bd7d-65c43249a46f` |
| BLLD_2019 | 123/-/- | Chưa gán nhãn | `0625a584-8e80-4cfa-83a0-c058c9471096` |
| BLLD_2019 | 122/1/- | Chưa gán nhãn | `5f3cd296-055a-430f-92a9-e9885cc6078f` |
| BLLD_2019 | 118/-/- | Chưa gán nhãn | `1186184d-60aa-4909-b8e8-850330f433d2` |
| NQCT | 13/-/- | Chưa gán nhãn | `abcf16e4-dd41-44e2-a9de-b3d700c82926` |
| NQCT | 10/-/- | Chưa gán nhãn | `2f91a733-3f9e-4e9c-a593-ef57cd51abef` |
| NQCT | 14/-/- | Chưa gán nhãn | `d82c0638-7939-4a4a-97d1-961074d3d1f1` |
| NQCT | 12/-/- | Chưa gán nhãn | `e37b5b35-86d1-4991-aa97-76e07c5f53a4` |
| BLLD_2019 | 117/-/- | Chưa gán nhãn | `e1b907a2-ba21-4c04-89dc-b8289c15fbbb` |
| NQCT | 16/-/- | Chưa gán nhãn | `e295a845-d11e-47dc-80ff-a1e9cda1927c` |
| NQCT | 2/-/- | Chưa gán nhãn | `cf5db6c1-2585-4fbb-ad32-51b6be2be3ef` |

### Q20

Tìm căn cứ về xử lý kỷ luật lao động cho vụ việc này.

Ngày dùng để lọc: 2000-01-01.

- Đơn vị quan trọng bị thiếu: [].
- Lỗi phiên bản/ngày: [].
- Đoạn bị thiếu hoặc thay đổi nội dung: [].
- Trạng thái suy giảm: [].
- Cảnh báo gói chứng cứ: ['MISSING_INTERNAL_RULE', 'MISSING_AUTHORITY'].
- Số đoạn chưa gán nhãn: 0.

| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |
| --- | --- | --- | --- |

## Giới hạn

- Ngày hiệu lực là metadata của ứng dụng, chưa được xác minh như kết luận pháp lý. Ngày của các ca là giá trị giả lập được khai báo riêng.
- Bộ nhãn được tạo trước khi chạy retrieval; không dùng đầu ra mô hình làm đáp án. Nhãn vẫn cần HR/pháp chế rà soát.
- Đủ bộ nhãn chỉ có nghĩa giữ đủ nhóm chứng cứ tối thiểu đã định nghĩa, không chứng minh đủ mọi căn cứ pháp lý.
- Các ca chỉ đo graph truy xuất thật với giao dịch chỉ đọc; không đo synthesis, lưu hồ sơ, hội thoại đầu cuối hoặc phê duyệt.
- Lỗi xử lý có điểm null; đầu ra suy giảm vẫn được chấm như quan sát thực tế và được đếm riêng.
