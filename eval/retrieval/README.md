# Đánh giá chất lượng truy xuất

Bộ đánh giá mới gồm **20 ca, 30 đơn vị chứng cứ và một ảnh chụp corpus thực tế**.
Có 5 ca dùng câu mô tả sự việc từ các DOCX trong `golden_dataset/`, 14 ca tổng
hợp có nhãn chứng cứ cụ thể và 1 ca âm tính có kiểm soát. Nhãn được chọn trước
khi chạy truy xuất, không lấy kết quả xếp hạng hiện tại làm đáp án.

**Toàn bộ nhãn hiện là bản nháp chờ HR/pháp chế rà soát.** “Đủ bộ chứng cứ” trong
báo cáo chỉ có nghĩa giữ đủ nhóm chứng cứ tối thiểu đã gán nhãn, không chứng minh
đủ mọi căn cứ để kết luận hoặc ra quyết định pháp lý.

## Tệp và phạm vi

| Tệp | Nội dung |
| --- | --- |
| `snapshot.py` | Chụp chunk, metadata, mã băm vector và dẫn chiếu bằng giao dịch chỉ đọc |
| `corpus_snapshot.json` | Ảnh chụp kho truy xuất đang chạy, kèm mã băm để tái lập |
| `build_dataset.py` | Tạo nhãn nháp từ các đơn vị chứng cứ được chọn thủ công và nguồn tình huống |
| `golden.json` | Query, ngày dùng để lọc, tình tiết, bộ chứng cứ chấp nhận được và nhãn liên quan |
| `benchmark.py` | Chạy graph retrieval thực tế hoặc chấm ngoại tuyến |
| `results/golden_live/` | Lần chạy ban đầu chưa điều tiết, có các ca Cohere 429 và kết quả suy giảm |
| `results/golden_paced/` | Lần chạy riêng có giãn cách request; không ghi đè lần chạy ban đầu |
| `evaluate.py` | Công cụ cũ chỉ nhận nhãn UUID đã được chuyên gia duyệt; giữ nguyên cổng kiểm tra |

Graph được đo chính là `build_retrieval_graph` trong ứng dụng:

```text
Vector + BM25 + từ khóa → RRF → rerank hạt giống → dẫn chiếu một bước
  → rerank theo khía cạnh → chọn chứng cứ → tìm bổ sung tối đa một lượt
  → chọn lại / dự phòng theo mục lục khi cần
```

Bộ chạy không gọi lớp ghi nhật ký nghiệp vụ `search_policies`, không sinh đánh
giá vụ việc và không ghi database. Embedding query vẫn đi qua client thật của
ứng dụng và ghi nhật ký API cục bộ như bình thường. Mistral và Cohere có thể
phát sinh phí.

## Corpus thực tế được cố định

Ảnh chụp đi kèm có **1.307 chunk**:

- BLLD: 381.
- ND145: 377.
- ND283: 531.
- Nội quy NQCT: 18.

Bảng `chunk_references` trong DB chụp có **0 cạnh**. Vì vậy bộ chạy vẫn đi qua
node mở rộng đồ thị, nhưng không thể đo lợi ích của dẫn chiếu khi dữ liệu đồ thị
trống. Chỉ số tăng recall từ đồ thị được để trống, không tự diễn giải thành
“đồ thị không có tác dụng”. Không tự chạy ETL để thêm cạnh trong lúc đánh giá.

Số lượng và nội dung DB khác một số tệp chia đoạn cục bộ, đặc biệt là nội quy.
Nhãn retrieval được gắn với **UUID, nội dung, metadata và mã băm vector trong DB
đang phục vụ**, không tự dùng UUID hoặc số lượng từ kho JSON khác.

Metadata đang lưu cho ND145 có ngày kết thúc 09/09/2026, tính cả ngày. Các ca
Q15 và Q19 dùng hai phía của mốc này. Đây chỉ là kiểm tra nhất quán với bộ lọc
ứng dụng; chưa xác minh rằng các ngày hoặc quan hệ thay thế văn bản đó đúng
pháp luật. Ngày truy xuất của các ca được khai báo là giá trị giả lập, không
phải ngày đã được xác nhận từ DOCX tình huống.

## Kiểm tra bộ dữ liệu mà không gọi API

Chạy từ thư mục gốc của kho mã:

```bash
python -m eval.retrieval.benchmark --validate-only
```

Lệnh kiểm tra mã băm ảnh chụp, UUID và nội dung chứng cứ, cấu trúc nhãn, nguồn
DOCX và điều kiện phiên bản/ngày trong ảnh chụp. Nó không kết nối DB để xác nhận
trạng thái mới nhất và chưa chấm retrieval.

## Chạy truy xuất thật với nhãn nháp

Dùng môi trường Python có các thư viện ứng dụng, DB hiện tại và khóa
`MISTRAL_API_KEY`, `COHERE_API_KEY`. Lệnh sau có gọi API:

```bash
python -m eval.retrieval.benchmark --live --allow-draft \
  --rerank-interval 7 --output-dir eval/retrieval/results/lan_chay_moi
```

`--allow-draft` chỉ cho phép xem trước số đo và luôn ghi trạng thái nhãn nháp.
Nó không biến nhãn thành nhãn chuyên gia. Không có cờ này, bộ chạy từ chối chấm
nhãn chưa được duyệt. Cổng nhãn của `evaluate.py` cũ không bị thay đổi.

Bộ chạy chụp lại DB trước khi gọi API và sau khi thu thập xong. Nội dung, vector,
metadata và đồ thị phải khớp ảnh chụp đã gán nhãn. Nếu thay đổi hoặc chưa xác nhận
được trạng thái cuối, công cụ dừng chấm thay vì dùng nhãn cũ cho corpus mới.
Mỗi ca dùng một giao dịch `READ ONLY`; không cập nhật các bảng nghiệp vụ.

### Điều tiết Cohere

Cohere công bố giới hạn Rerank của khóa trial là **10 request/phút**; khóa
production có hạn mức khác. Xem [tài liệu giới hạn chính thức của Cohere](https://docs.cohere.com/v2/docs/rate-limits).
Một ca có một lần rerank hạt giống, bốn lần theo khía cạnh và có thể thêm các lần
rerank sau tìm bổ sung, nên số ca không bằng số HTTP request.

Lần chạy ban đầu phát sinh HTTP 429 sau hai ca đầu. Cờ `--rerank-interval 7`
giãn cách thời điểm bắt đầu các request trong chính bộ đánh giá. Bộ điều tiết
chỉ bọc hàm rerank gốc trong tiến trình này, giữ nguyên query, đoạn đầu vào,
điểm và graph; không sửa thuật toán trong `src/`. Đầu vào rỗng không bị tính là
một request. Không tự gọi lại API lỗi để làm đẹp số đo.

**Thời gian đo bao gồm chờ điều tiết.** Không dùng số này làm độ trễ phục vụ
người dùng hoặc so trực tiếp với lần không điều tiết. Nếu nhiều tiến trình cùng
dùng một khóa, bộ điều tiết cục bộ không kiểm soát lưu lượng của tiến trình khác.
Hạn mức tháng vẫn là giới hạn riêng của tài khoản.

### Tiếp tục một lần thu thập

Mỗi ca được ghi ngay vào `runs.json`. Khi bị gián đoạn:

```bash
python -m eval.retrieval.benchmark --live --allow-draft --resume \
  --rerank-interval 7 --output-dir eval/retrieval/results/lan_chay_moi
```

Cấu hình, nhãn và corpus phải khớp lần trước. Ca đã thu thập hoàn chỉnh được giữ
lại, kể cả khi trạng thái rerank suy giảm, để không âm thầm thay thế kết quả xấu.
Muốn đo lại các ca đó, tạo một lần chạy riêng. Ca lỗi xử lý hoặc chưa thu thập
được thực hiện lại. Mặc định giới hạn 150 giây cho mỗi graph; có thể điều chỉnh
`--timeout` khi cần, đặc biệt nếu tăng khoảng cách request.

## Chấm lại kết quả đã lưu

Không gọi DB hoặc API:

```bash
python -m eval.retrieval.benchmark --allow-draft \
  --runs eval/retrieval/results/golden_paced/runs.json \
  --output-dir eval/retrieval/results/cham_lai
```

Tệp kết quả phải có cùng mã băm bộ dữ liệu, corpus và đầu vào từng ca, đồng thời
đã xác nhận corpus giữ nguyên sau thu thập. Thiếu ca được ghi là lỗi, điểm
`null`; không thay thành 0 hoặc tính là đạt.

Mỗi lần chấm xuất:

- `scores.json`: số đếm, trung bình kèm mẫu số, recall từng giai đoạn, lỗi và
  danh sách UUID được chọn.
- `report.md`: báo cáo tiếng Việt, danh sách chứng cứ, mức liên quan và các
  đơn vị quan trọng bị thiếu theo từng query.
- `runs.json` chỉ được tạo khi gọi thật: pool của các nhánh, RRF, hạt giống,
  mở rộng/tìm bổ sung, thứ hạng, điểm khía cạnh và toàn văn các đoạn cuối.

Mã thoát 0 cho biết việc thu thập không có lỗi hoặc trạng thái suy giảm và corpus
được giữ nguyên; **không có nghĩa mọi query tìm đủ chứng cứ hoặc nhãn đã đúng**.
Số ca đạt phép kiểm tra chứng cứ được báo riêng ở `passed_labeled_checks`.

## Cách đọc nhãn và chỉ số

Một đơn vị chứng cứ là một điều/khoản/điểm có một hoặc nhiều chunk. Để đánh dấu
đủ đơn vị, phải giữ đủ các chunk thành viên. Khi đổi cách chia đoạn, cần ánh xạ
lại đơn vị và rà soát nhãn; không tự coi UUID mới là tương đương.

Mỗi ca có một hoặc nhiều `evidence_bundles`, là các phương án chấp nhận được cho
câu hỏi hẹp đã ghi. Chỉ cần đủ một phương án; không bắt buộc lấy hợp mọi phương
án. Ví dụ Q15 chấp nhận một trong hai đoạn có thời hạn thông báo cuộc họp. Các
`critical_units` là chứng cứ có điều kiện hoặc ngoại lệ cần giữ, không được che
bằng điểm trung bình tốt của ca khác.

| Chỉ số | Cách hiểu |
| --- | --- |
| `candidate_recall` | Tỷ lệ chunk tham chiếu tìm thấy trong hợp pool RRF và pool mở rộng/tìm bổ sung, lấy phương án tốt nhất |
| `final_recall` | Tỷ lệ chunk tham chiếu còn lại trong gói chứng cứ cuối, lấy phương án tốt nhất |
| `complete_labeled_bundle` | Có giữ đủ một bộ chứng cứ tối thiểu đã gán nhãn không |
| `critical_chunk_recall` | Tỷ lệ chunk thuộc các đơn vị quan trọng được giữ |
| `labeled_precision_lower_bound` | Số đoạn có nhãn liên quan dương tính / số đoạn cuối; đây là cận dưới theo nhãn chưa đầy đủ |
| `judged_precision` | Số đoạn có nhãn liên quan dương tính / số đoạn cuối đã được gán nhãn |
| `judgment_coverage` | Số đoạn cuối đã gán nhãn / tổng số đoạn cuối; cần đọc cùng `judged_precision` |
| `ndcg_lower_bound` | Chất lượng thứ tự theo mức liên quan 0–3; đoạn chưa gán nhãn tạm nhận 0 trong phép tính, không phải kết luận không liên quan |
| `date_eligibility_pass` | Mọi đoạn cuối đều đúng trạng thái, ngày, nguồn còn hoạt động và điều kiện tài liệu của ứng dụng |
| `passage_fidelity_pass` | Toàn văn chunk nguồn còn nguyên trong đoạn thực sự được trả về; đúng UUID nhưng cắt mất ngoại lệ vẫn chưa đạt |
| `graph_recall_gain` | Mức tăng recall từ ứng viên có nguồn đồ thị, không trộn với ứng viên BM25 tìm bổ sung; để trống nếu không có cạnh |
| `expected_empty_pass` | Ca Q20 có ngày nằm ngoài toàn bộ corpus trả về rỗng; không suy diễn rằng không có luật ngoài corpus |

Nhãn liên quan chỉ bao phủ các đơn vị dương tính đã chọn, một số đoạn bổ trợ và
một nhóm âm tính cụ thể. Chưa gán nhãn toàn bộ các đoạn có thể liên quan. Vì vậy
`judged_precision = 1` với `judgment_coverage` thấp không chứng minh retrieval có
precision thực tế bằng 1. Cần mở rộng nhãn các đoạn chưa được chấm, với người
rà soát không nhìn trước tên cấu hình đang so sánh.

Đầu ra suy giảm do lỗi API vẫn được đo như quan sát thực tế và được đếm riêng;
không được trình bày như kết quả của rerank khỏe. Recall ứng viên cao nhưng
recall cuối thấp chỉ ra chứng cứ bị mất ở giai đoạn sau; xem `stage_recall`,
`health_gaps`, `evidence_gaps` và danh sách được chọn để chẩn đoán.

## Chụp lại corpus và cập nhật nhãn

Chỉ đọc DB, không gọi mô hình:

```bash
python -m eval.retrieval.snapshot --output /tmp/retrieval-corpus.new.json
python -m eval.retrieval.build_dataset \
  --snapshot /tmp/retrieval-corpus.new.json --output /tmp/retrieval-golden.new.json
```

Nguồn phải được đối chiếu: UUID, nội dung và phiên bản trong DB; nguồn chính
thống và hiệu lực; các điều kiện/ngoại lệ; bộ chứng cứ chấp nhận được; mức liên
quan và nhãn âm tính. Ngày và corpus demo hiện tại chưa được bộ đánh giá xác
nhận là nguồn pháp lý đáng tin cậy.

Sau khi thật sự được duyệt, đặt `reference_status` của từng ca thành
`expert_reviewed` và điền `reviewer`; khi đó không cần `--allow-draft`. Không tự
gán trạng thái chuyên gia chỉ vì script chạy được. Việc đổi nhãn cần lần thu
thập tương ứng, hoặc giữ bản nhãn cũ để tái lập lần đo trước. Các công cụ tạo
nguồn/nhãn từ chối ghi đè trừ khi chỉ định `--overwrite`.

## Công cụ cũ dành cho nhãn chuyên gia

`evaluate.py` cũ tiếp tục nhận JSON array gồm `case_id`, `reference_status`,
`incident_date`, `description`, `family`, `facts`, `evidence_bundles` (UUID),
`critical_chunk_ids` và tùy chọn `relevance` (UUID → mức 0–3). Nó vẫn từ chối
nhãn khác `expert_reviewed`:

```bash
python -m eval.retrieval.evaluate --references PATH_TO_REVIEWED_JSON --validate-only
```

Không đưa trực tiếp `golden.json` mới vào công cụ cũ: định dạng đơn vị chứng cứ
và cổng nhãn khác nhau. Dùng `benchmark.py` cho bộ dữ liệu mới.

## Kiểm tra bộ chấm

```bash
python -m pytest tests/test_retrieval_benchmark.py -q
```

Kiểm thử không gọi mạng hoặc DB. Chúng bao gồm phương án chứng cứ thay thế,
ngoại lệ bị mất, đơn vị nhiều chunk, nội dung bị cắt dù UUID đúng, ngày hiệu lực,
nhãn chưa đầy đủ, thứ tự nDCG, ca rỗng, lỗi API, corpus thay đổi và điều tiết
request giữ nguyên đầu vào/đầu ra.
