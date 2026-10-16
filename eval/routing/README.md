# Đánh giá định tuyến và trích xuất tình tiết

Bộ đánh giá gồm **48 ca nháp**: 30 ca định tuyến và 18 ca trích xuất, hợp nhất tình
tiết. Trong đó, 5 ca tình tiết lấy câu mô tả từ 5 biên bản DOCX trong
`golden_dataset/`; 43 ca còn lại là tình huống tổng hợp theo hợp đồng ứng dụng.
Các ca tổng hợp không phải hội thoại vận hành thực tế. Nhãn chưa được chuyên gia
rà soát và không được tạo bằng cách sao chép đầu ra của mô hình.

## Các tệp chính

| Tệp | Mục đích |
| --- | --- |
| `golden.json` | Đầu vào, ngữ cảnh, tình tiết đang lưu và nhãn mong đợi |
| `build_dataset.py` | Tạo lại nhãn nháp, trích nguồn DOCX độc lập với mô hình |
| `evaluate.py` | Thu thập đầu ra mô hình thật hoặc chấm lại kết quả đã lưu |
| `results/golden_live/runs.json` | Đầu ra thô, quyết định sau kiểm tra Python, cấu hình và thời gian từng ca |
| `results/golden_live/scores.json` | Chỉ số, số đếm và lỗi từng ca |
| `results/golden_live/report.md` | Báo cáo tiếng Việt |
| `run.py`, `cases.json`, `results.json` | Bộ kiểm tra nhanh 10 ca có trước; được giữ riêng |
| `check_safety.py`, `safety-results.json` | Kiểm tra nhanh điều tiết nội dung có trước; không thay thế bộ đánh giá này |

## Kiểm tra bộ dữ liệu trước khi chạy

Chạy từ thư mục gốc của kho mã:

```bash
python -m eval.routing.evaluate --validate-only
```

Lệnh này kiểm tra cấu trúc nhãn, ID, mã SHA-256 của nguồn DOCX và việc đầu vào
khớp trích đoạn đã lưu. Nó chưa đánh giá mô hình hoặc xác nhận nhãn đúng về
ngữ nghĩa. Bộ chấm ngoại tuyến chỉ dùng thư viện chuẩn của Python.

## Chạy với mô hình thật

Dùng môi trường Python của ứng dụng và cấu hình `LLM_PROVIDER`, khóa API tương
ứng, cùng model hội thoại trong `.env`. Không đổi model chỉ để chạy bộ chấm.
Lệnh sau gọi API và có thể phát sinh phí:

```bash
python -m eval.routing.evaluate --live
```

Mặc định chạy tối đa 2 ca đồng thời, giới hạn 75 giây cho mỗi ca. Bộ định tuyến
vẫn sử dụng bước kiểm tra lại ngữ nghĩa và giới hạn thời gian nội bộ của ứng
dụng. Bộ lập kế hoạch vẫn dùng cơ chế thử lại có sẵn. Vì vậy số ca không bằng số
HTTP request. Không gọi truy xuất, tạo câu trả lời, ghi cơ sở dữ liệu hoặc gửi
hồ sơ đi duyệt.

Nếu muốn lưu lần chạy mới vào thư mục riêng:

```bash
python -m eval.routing.evaluate --live --output-dir eval/routing/results/lan_chay_moi
```

Mỗi ca hoàn tất đều được ghi lại ngay. Khi tiếp tục, các ca đã hoàn thành được
giữ lại; ca lỗi hoặc chưa chạy sẽ được thực hiện lại:

```bash
python -m eval.routing.evaluate --live --resume
```

Công cụ chỉ cho tiếp tục khi bộ dữ liệu và cấu hình khớp lần thu thập trước.
Không tự ghi đè một lần chạy có sẵn nếu chưa có `--resume`. Khi so sánh model,
lưu từng lần ở thư mục riêng và giữ nguyên bộ dữ liệu, nhãn, cấu hình thử nghiệm.

## Chấm lại mà không gọi API

```bash
python -m eval.routing.evaluate \
  --runs eval/routing/results/golden_live/runs.json \
  --output-dir eval/routing/results/cham_lai
```

Mã băm bộ dữ liệu phải khớp bản đã dùng thu thập; mã băm đầu vào của từng ca
cũng được đối chiếu. Thiếu đầu ra không được tính là đạt. Lỗi API, hết thời
gian, lỗi cấu trúc và phương án dự phòng có điểm `null`; báo cáo ghi riêng số ca
hoàn thành và số lỗi. Độ chính xác ngữ nghĩa được tính trên các ca hoàn thành,
không dùng lỗi xử lý để tạo một dự đoán đúng hoặc sai giả tạo. Kết quả tổng thể
vẫn là chưa đạt nếu còn ca lỗi hoặc ca không đạt yêu cầu.

Mã thoát 0 nghĩa là toàn bộ ca đều đạt; 1 nghĩa là còn ca sai, lỗi hoặc chưa qua
điều kiện rà soát. Bộ dữ liệu hoặc tệp đầu vào sai cấu trúc sẽ gây lỗi rõ ràng.

## Phần định tuyến đo gì

30 ca bao phủ cả 10 nhánh trong `Route`: xã giao, hỗ trợ sử dụng hệ thống, hỏi
thông tin hồ sơ, cung cấp tình tiết, hỏi nội quy, thao tác quy trình, tra cứu bên
ngoài, hỏi làm rõ, thao tác không được phép và khả năng chưa được hỗ trợ.

Mỗi ca gồm tin nhắn hiện tại, trạng thái đầu vào và nhánh mong đợi; một số ca
còn ràng buộc hành động và việc giữ/hủy tác vụ. Ví dụ:

- “AI có quyền phê duyệt hồ sơ không?” là câu hỏi về quyền hạn của sản phẩm.
- “Phê duyệt hồ sơ này ngay giúp tôi” là yêu cầu thực thi ngoài thẩm quyền.
- “Đã lập biên bản” cung cấp tình tiết; “lập biên bản giúp tôi” yêu cầu chuẩn bị
  tài liệu; “lập biên bản cần bước nào theo luật” hỏi quy định.
- Lượt cảm ơn không được tiếp tục yêu cầu lập biên bản cũ.
- Hủy tác vụ đang chờ khác với đóng hoặc xóa hồ sơ.

Công cụ gọi `route_turn`, rồi `_decide_intent_route` và `route_after_intent` của
ứng dụng. Nó ghi cả nhánh ban đầu, trạng thái kiểm tra lại, nhánh cuối, cạnh đồ
thị và hành động. Giả thuyết từ khóa chỉ đi vào cơ chế kiểm tra lại của ứng dụng;
không được dùng như mô hình giả hoặc đáp án thay thế.

Các chỉ số gồm độ chính xác nhánh cuối, tỷ lệ đạt cả nhánh/hành động/hợp đồng,
precision/recall/F1 theo nhánh, F1 trung bình giữa các lớp có mẫu và bảng nhầm
lẫn trong JSON. Phương án dự phòng do lỗi không được tính là ca “clarify” đúng.

## Phần tình tiết đo gì

18 ca gọi trực tiếp `plan_turn`, sau đó `apply_decision`, `reconcile_plan`,
`memory_patch` và cổng sau trích xuất. Các ca tình tiết được đo độc lập với bộ
định tuyến để có thể tìm lỗi riêng của thành phần này. Đây chưa phải phép đo
khả năng định tuyến đúng rồi trích xuất đúng liên tiếp trong toàn bộ hội thoại.

Đầu vào cung cấp lược đồ tình tiết đang hoạt động, nhóm vụ việc, dữ liệu đã lưu
và tác vụ đang chờ. Các thông tin này mô phỏng trạng thái hợp lệ của một hồ sơ,
không phải nhãn đáp án gửi cho mô hình. Đáp án mong đợi chỉ được đọc ở bộ chấm.
Bộ này chưa đo khả năng tự tạo lược đồ động hoặc tự nhận diện nhóm vụ việc.

Hai lớp đầu ra được chấm riêng:

1. **Đầu ra mô hình:** các tình tiết đề xuất/sửa, giá trị và trích dẫn bằng chứng.
2. **Sau kiểm tra Python:** giá trị đã hợp nhất, trạng thái xác nhận, tình tiết
   còn thiếu, trạng thái khóa và việc giữ tác vụ đang chờ.

Các ca kiểm tra dữ liệu còn thiếu, phủ định, loại hợp đồng, số ngày/lần, sửa giá
trị cũ, xác nhận dữ liệu chờ, tiếp tục tác vụ và yêu cầu bịa tình tiết. Năm ca
DOCX chỉ gửi các câu được chọn, không gửi tiêu đề biên bản rồi suy diễn rằng mọi
bước quy trình đã hoàn tất. Mỗi nguồn có đường dẫn, mã băm và vị trí đoạn `w:p`
trong `word/document.xml`, bắt đầu từ 1.

Các chỉ số gồm precision/recall/F1 cho cặp khóa–giá trị trước và sau kiểm tra,
tỷ lệ ca đạt toàn bộ ràng buộc và tỷ lệ trích dẫn khớp nguyên văn tin nhắn hiện
tại. Sai giá trị vừa tính là dự đoán sai vừa tính là bỏ sót giá trị đúng. Tình
tiết thừa được tính vào mẫu số precision. Giá trị số không được so khớp chuỗi
con: `50 ngày` không khớp `5 ngày`.

Bộ chấm dùng các biến thể giá trị được khai báo và chuẩn hóa độc lập, không dùng
hàm chuẩn hóa của ứng dụng để tự chấm ứng dụng. Với `violation_summary`, nhãn
`contains_all` yêu cầu các cụm được chỉ định; đây là kiểm tra cơ học, không thay
thế đánh giá ngữ nghĩa của chuyên gia. Việc trích dẫn khớp tin nhắn cũng không tự
chứng minh tình tiết suy ra là đúng.

## Rà soát và cập nhật nhãn

Đọc tin nhắn, ngữ cảnh và nhãn trong `golden.json`, đối chiếu hợp đồng sản phẩm
và các DOCX được dẫn nguồn. Với ca đã duyệt, đặt `review_status` thành `reviewed`
và điền `reviewer`. Với ca lấy từ DOCX, điền thêm `source.reviewed_source_sha256`
bằng mã băm nguồn đã kiểm tra. Có thể bắt buộc trạng thái đã duyệt bằng
`--require-reviewed`.

Tạo một bản nháp mới mà không ghi đè bản đang được rà soát:

```bash
python -m eval.routing.build_dataset --output /tmp/routing-golden.new.json
```

Công cụ chỉ ghi đè nếu truyền `--overwrite`; thao tác này làm mất sửa đổi nhãn
thủ công. Sau khi đổi nhãn, thu thập một lần chạy khớp bộ dữ liệu mới; bộ chấm
không âm thầm trộn các phiên bản. Khi tinh chỉnh prompt, giữ một tập hội thoại
chưa dùng để chỉnh prompt; 48 ca công khai hiện tại chủ yếu phục vụ hồi quy và
chẩn đoán lỗi, chưa đại diện cho dữ liệu vận hành.

## Kiểm tra bộ chấm

```bash
python -m pytest tests/test_routing_evaluation.py -q
```

Kiểm thử không gọi API. Chúng cố ý tạo sai nhánh, sai hành động, thay đổi tác vụ,
sai giá trị, bịa tình tiết, bằng chứng ngoài tin nhắn, lỗi khóa dữ liệu, mất tác
vụ, lỗi nguồn và lỗi xử lý để kiểm tra rằng bộ chấm không báo thành công giả.
