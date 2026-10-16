# Đánh giá kho tri thức và quy trình nạp dữ liệu

Bộ đánh giá này đối chiếu các đoạn văn từ nguồn độc lập với kết quả chia đoạn
(chunk). Một đoạn nguồn có thể nằm trong nhiều chunk, kể cả khi bị tách giữa một
từ. Các phép kiểm tra bao gồm bảo toàn nội dung, gán đúng nguồn, danh mục điều,
yêu cầu ngữ cảnh cụ thể và một số dẫn chiếu đã gán nhãn. Bộ đánh giá không gọi
LLM, API tạo vector hay cơ sở dữ liệu.

Dữ liệu đi kèm gồm **16 ca đánh giá cấp điều ở trạng thái nháp, 189 đoạn văn
nguồn và 5 nhãn dẫn chiếu cần tìm, thuộc 4 văn bản**. Danh mục điều trong phần
chính của từng văn bản cũng được cố định: BLLD có 220 điều, ND145 có 115 điều,
ND283 có 68 điều và nội quy có 82 điều. Các số liệu này được trích từ DOCX gốc
và Markdown nội quy do dự án biên soạn, không lấy từ kết quả chia đoạn. Việc
liệt kê dừng khi số điều bắt đầu lại ở phụ lục. Trích xuất độc lập vẫn có thể
sai và cần đối chiếu nguồn; đây chưa phải kết quả được chuyên gia hoặc pháp chế
duyệt.

## Chạy đánh giá trên dữ liệu đã lưu

Chạy từ thư mục gốc của kho mã:

```bash
python -m eval.ingestion.evaluate
```

Bộ chấm chỉ sử dụng thư viện chuẩn của Python. Nó đọc
`eval/ingestion/golden.json` và `data/chunk/chunks_*.json`, rồi ghi kết quả vào
`eval/ingestion/results/saved_corpus/report.md` và `scores.json`.

Mã thoát **0** nghĩa là mọi phép kiểm tra đã định nghĩa đều đạt; **1** nghĩa là
có phép kiểm tra hoặc điều kiện rà soát chưa đạt. Dữ liệu đầu vào sai cấu trúc
sẽ gây lỗi. Các lần chạy với nhãn nháp luôn ghi rõ trạng thái này, kể cả khi
mọi phép kiểm tra đều đạt. Thiếu tệp kết quả, đầu ra rỗng, mã băm nguồn thay đổi
hoặc lỗi chuyển đổi đã được ghi nhận đều không được tính là thành công.

## Chạy lại bằng mã xử lý thực tế

Công cụ thu thập đầu ra cần các thư viện Python hiện có của ứng dụng. Dùng thư
mục riêng để tránh ghi đè kho dữ liệu đã cố định.

Chạy lại bước chia đoạn, vá công thức và trích dẫn chiếu của quy trình xây dựng
ngoại tuyến, bắt đầu từ Markdown **đã làm sạch**:

```bash
python -m eval.ingestion.capture --mode offline --output-dir /tmp/p029-ingestion-offline
python -m eval.ingestion.evaluate --chunks-dir /tmp/p029-ingestion-offline --output-dir eval/ingestion/results/offline_replay
```

Chạy lại bước chuyển đổi, làm sạch, chia đoạn và trích dẫn chiếu của luồng tải
lên dành cho quản trị viên, bắt đầu từ DOCX gốc hoặc Markdown đã biên soạn:

```bash
python -m eval.ingestion.capture --mode upload --output-dir /tmp/p029-ingestion-upload
python -m eval.ingestion.evaluate --chunks-dir /tmp/p029-ingestion-upload --output-dir eval/ingestion/results/upload_replay
```

Nếu thiếu các thư viện bổ sung để MarkItDown đọc DOCX, công cụ ghi nhận lỗi và
trả mã thoát 1. Nó không tự thay thế bằng Markdown đã lưu. Để chủ động bỏ qua
chuyển đổi và chỉ kiểm tra tiền xử lý, chia đoạn của luồng tải lên:

```bash
python -m eval.ingestion.capture --mode upload --use-saved-markdown --output-dir /tmp/p029-ingestion-upload-markdown
python -m eval.ingestion.evaluate --chunks-dir /tmp/p029-ingestion-upload-markdown --output-dir eval/ingestion/results/upload_markdown_replay
```

Mỗi lần thu thập đầu ra ghi một tệp `capture.json` chứa phạm vi, mã băm đầu vào,
số lượng và lỗi. Công cụ xử lý trong bộ nhớ hoặc thư mục đầu ra; không gọi dịch
vụ tải lên, hàm ghi cơ sở dữ liệu hay dịch vụ tạo vector. Chế độ ngoại tuyến
không chạy lại chuyển đổi và làm sạch. Chế độ tải lên từ Markdown có sẵn không
chạy lại chuyển đổi DOCX gốc. Không bắt buộc số chunk phải trùng nhau: chênh lệch
377 và 386 chunk là thông tin chẩn đoán, không tự động bị tính là lỗi.

## Ý nghĩa của một ca trong bộ dữ liệu chuẩn

Mỗi ca xác định văn bản, điều và vị trí đoạn văn hoặc dòng trong nguồn, kèm
đầy đủ nội dung mong đợi. Với DOCX, `source_index` là thứ tự phần tử `w:p` trong
`word/document.xml`, bắt đầu từ 1. Với Markdown, đó là số dòng, bắt đầu từ 1.
Bộ dữ liệu không quy định UUID của chunk đầu ra hoặc vị trí bắt buộc phải tách.

Ví dụ, `ND145_2020-A003` chứa đoạn dẫn và ba khoản thực tế của Điều 3. Ca này
mong đợi văn bản `145/2020/NĐ-CP`, Điều 3 và dẫn chiếu tới khoản 1 Điều 12 Bộ
luật Lao động. Một chunk chứa cả điều hoặc nhiều chunk nhỏ được gán đúng nguồn
đều có thể đáp ứng yêu cầu.

Quy trình chấm thực hiện các bước sau:

1. Kiểm tra mã băm tệp gốc và danh mục điều của từng văn bản.
2. Ghép nội dung chính theo thứ tự trong từng văn bản đầu vào, gộp phần chồng
   lặp khớp chính xác từ 24 ký tự đã chuẩn hóa trở lên. Vẫn truy vết được mỗi
   vùng nội dung thuộc những chunk nào.
3. Tìm từng đoạn nguồn trong nội dung chính, ngữ cảnh tiêu đề được kế thừa hoặc
   trường `chapeau_text` đã lưu. Một đoạn có thể trải qua nhiều chunk. Nội dung
   chỉ còn trong siêu dữ liệu được phân biệt với nội dung truy xuất có thể đọc;
   trường hợp này không đạt phép kiểm tra ngữ cảnh.
4. Tìm trong toàn bộ chunk của văn bản đầu vào, không chỉ các chunk được gán
   số điều mong đợi. Nhờ đó, đoạn bị gán sai điều vẫn có thể được tìm thấy và
   báo lỗi. Tệp đầu vào xác định nhóm văn bản.
5. Kiểm tra văn bản, loại văn bản, điều và các trường mô tả tương ứng; với chunk
   cấp khoản hoặc điểm, kiểm tra khoản và điểm nguồn. Chunk cấp điều có thể
   chứa nhiều khoản và để trống trường khoản, điểm. Số thứ tự có thể chuyển
   sang siêu dữ liệu; chunk cấp điều vẫn phải giữ số thứ tự nguồn. Thứ tự các
   đoạn trong nội dung chính cũng được kiểm tra.
6. Yêu cầu tiêu đề ngữ cảnh có thông tin văn bản và điều. Các điểm thuộc khoản
   1 Điều 49 ND283 còn phải giữ câu dẫn về mức tiền trong nội dung hoặc tiêu đề
   của từng chunk liên quan, để việc ghép đoạn khi chấm không che mất ngữ cảnh.
7. Kiểm tra 5 dẫn chiếu đã được gán nhãn cần có. Điều 1 BLLD là ca đối chứng
   không được có dẫn chiếu. Các dẫn chiếu khác nằm ngoài phạm vi nhãn; sự xuất
   hiện của chúng không tự động bị trừ điểm.
8. Báo các mảnh nội dung chính phát sinh hoặc bị sửa trong các điều được chọn,
   bằng cách so từng chunk liên quan với toàn bộ nội dung điều nguồn. Ký hiệu
   điểm do bộ chia đoạn thêm và số thứ tự được kiểm tra riêng về cấu trúc.
   Phép kiểm tra này đối chiếu nghiêm ngặt để chẩn đoán; không xác thực nội dung
   được thêm vào tiêu đề.

Chuẩn hóa loại bỏ khoảng trắng và định dạng trình bày Markdown, nhưng giữ dấu
Tiếng Việt, chữ hoa/thường, dấu câu, giá trị số và từ phủ định. So khớp được
thực hiện nghiêm ngặt, không dùng ngưỡng tương đồng gần đúng có thể chấp nhận
`30` thành `60`. Vì vậy, cách diễn đạt lại hợp lệ vẫn có thể cần rà soát thủ
công. Các cụm ngắn lặp lại có thể gây nhập nhằng nếu chưa có ánh xạ vị trí nguồn
thực sự; cần kiểm tra các chunk được báo là chứa nội dung.

## Đọc các chỉ số

| Chỉ số | Ý nghĩa |
| --- | --- |
| `span_preservation_rate` | Số đoạn được gán nhãn tìm thấy đầy đủ trong nội dung, tiêu đề hoặc siêu dữ liệu câu dẫn / tổng số đoạn được gán nhãn |
| `retrieval_visible_span_rate` | Số đoạn tìm thấy đầy đủ trong nội dung hoặc tiêu đề / tổng số đoạn được gán nhãn |
| `metadata_pass_rate_on_preserved_spans` | Số đoạn được bảo toàn có các chunk liên quan đạt kiểm tra gán nguồn và cấu trúc / số đoạn được bảo toàn |
| `context_pass_rate_on_preserved_spans` | Số đoạn được bảo toàn đạt yêu cầu ngữ cảnh và thứ tự cụ thể / số đoạn được bảo toàn |
| `positive_reference_recall` | Số dẫn chiếu đúng được tìm thấy / 5 dẫn chiếu mong đợi |
| Danh mục điều | Số điều chính mong đợi xuất hiện trong nhãn chunk, theo từng văn bản; không phản ánh độ chính xác toàn bộ nội dung |
| `chunks_with_unexpected_body_text` | Số chunk thuộc các điều được chọn có mảnh nội dung chính không được nội dung điều nguồn hỗ trợ |

Báo cáo trình bày số lượng và lỗi theo từng ca, gồm đầy đủ đoạn mong đợi, vị trí
nguồn và ID chunk thực tế liên quan. Đoạn bị thiếu không đồng thời được tính là
đạt kiểm tra siêu dữ liệu. Tệp JSON còn cố định mã băm bộ dữ liệu, mã băm các tệp
chunk đầu vào và phạm vi thu thập để có thể tái lập kết quả.

## Rà soát và mở rộng nhãn

Mở các tệp gốc đã cố định và kiểm tra nội dung, danh mục điều, cách nhóm đoạn,
nhãn khoản/điểm và đích dẫn chiếu đã gán nhãn. Bộ đánh giá chưa xác thực độc lập
ba tệp DOCX là văn bản chính thức. Markdown nội quy là nguồn do dự án biên soạn.
Bộ này chưa xác nhận ngày hiệu lực.

Với mỗi văn bản và ca đã rà soát, đặt `review_status` thành `reviewed`, điền
`reviewer`, rồi chép `source_sha256` đã cố định của văn bản vào
`reviewed_source_sha256`. Sau đó bật điều kiện bắt buộc đã rà soát:

```bash
python -m eval.ingestion.evaluate --require-reviewed
```

Để tạo lại một **bản nháp mới** từ các tệp nguồn gốc:

```bash
python -m eval.ingestion.build_dataset --output /tmp/ingestion-golden.new.json
```

Rà soát phần khác biệt so với bộ dữ liệu đã cố định. Không dựng lại đáp án mong
đợi từ chunk hiện tại chỉ để làm biến mất lỗi. Công cụ từ chối ghi đè bộ dữ liệu
có sẵn trừ khi truyền `--overwrite`; ghi đè sẽ làm mất các chỉnh sửa rà soát thủ
công. Giữ riêng các đơn vị nguồn chưa dùng khi tinh chỉnh bộ chia đoạn; 16 ca
hồi quy công khai này không phải mẫu ước lượng khách quan độ chính xác vận hành.

## Giới hạn

Bộ đánh giá không xác nhận tính đúng đắn pháp lý, khả năng áp dụng theo ngày,
toàn bộ nội dung mọi điều, độ chính xác dẫn chiếu trên toàn kho, nội dung thêm
vào tiêu đề hoặc siêu dữ liệu, mức đầy đủ của bảng/hình/phụ lục, khả năng sử dụng
ngữ nghĩa của mọi chunk, độ khớp cơ sở dữ liệu đang chạy, tính cập nhật hoặc số
chiều vector, hay chất lượng truy xuất và sinh câu trả lời. Mã băm khớp xác nhận
đúng tệp, không xác nhận nội dung đúng. Nội dung chính được thêm chỉ được kiểm
tra trong các điều lấy mẫu; phần khác vẫn cần rà soát. Phép kiểm tra ngữ cảnh
cha cụ thể không phải bộ phân tích tổng quát các quan hệ phụ thuộc pháp lý.

## Kiểm tra bộ chấm

```bash
python -m pytest tests/test_ingestion_evaluation.py -q
```

Các kiểm thử bao gồm tách/chồng lặp hợp lệ, sửa số, xóa ngoại lệ, thêm phủ định,
sai siêu dữ liệu, mất số thứ tự nguồn, thiếu hoặc thêm sai dẫn chiếu, thiếu ngữ
cảnh, đảo thứ tự, thay đổi nguồn, chunk trùng hoặc rỗng, thiếu đầu ra thu thập
và khả năng tạo lại bộ nhãn nháp giống nhau.
