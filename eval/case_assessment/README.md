# Đánh giá RAG bằng RAGAS

Bộ kiểm thử gồm 5 vụ việc HR (CA01–CA05). Script chạy truy xuất và đánh giá vụ việc của ứng dụng trên database hiện tại, sau đó chấm bằng RAGAS. Đây là đánh giá các thành phần RAG, chưa bao gồm toàn bộ luồng chat/xác nhận của HR.

## 1. Chuẩn bị

Chạy các lệnh từ thư mục gốc repo, trong môi trường Python có các dependency của ứng dụng:

```bash
python -m pip install -r eval/case_assessment/requirements.txt
```

Trong `.env`, kiểm tra:

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: database của RAG.
- `MISTRAL_API_KEY`, `MODEL_NAME`: dùng cho embedding và tạo câu trả lời.
- `RAGAS_JUDGE_MODEL`: tên model dùng để chấm. Nếu không đặt, provider Mistral dùng `MODEL_NAME`.

Database phải hoạt động. Các lệnh tạo câu trả lời và chấm điểm có gọi API, có thể phát sinh phí.

## 2. Kiểm tra dữ liệu tham chiếu

RAG đọc bảng `document_chunks` trong database. `ragas_dataset.json` chứa `reference_contexts` được xây dựng từ bản chụp `policy_snapshot.json`.

Trước khi đánh giá trên corpus hiện tại, đối chiếu từng `chunk_id` trong `reference_contexts` với database:

- Chunk còn tồn tại; nội dung, mã chính sách, điều và khoản khớp.
- Chính sách có `is_active=true`; phiên bản có `status=ACTIVE` và còn hiệu lực tại `incident_date` trong `source_metadata.json`.
- Tài liệu có `ingest_status` là `CHUNKED` hoặc `EMBEDDED`.

Repo hiện chưa có script riêng tự động đối chiếu này. Nếu corpus thay đổi, cần rà soát và cập nhật chứng cứ cùng đáp án tham chiếu trước khi chấm. Không đưa đáp án kiểm thử vào corpus truy xuất.

Kiểm tra cấu trúc dataset:

```bash
python eval/case_assessment/evaluate_ragas.py --validate-only
```

**Lệnh này chỉ kiểm tra cấu trúc và mức sẵn sàng chấm, không đối chiếu database.** `response` và `retrieved_contexts` là `null` trước khi chạy RAG là bình thường.

## 3. Chạy đánh giá

Chạy truy xuất thực tế, tạo câu trả lời và chấm cả 4 chỉ số:

```bash
python eval/case_assessment/evaluate_ragas.py --generate-missing --provider mistral
```

Có thể chọn model chấm bằng `--judge-model TEN_MODEL`. Để lưu kết quả ở thư mục riêng, thêm `--output-dir eval/case_assessment/results/lan_chay_moi`.

Nếu muốn chạy RAG trước rồi chấm sau:

```bash
python eval/case_assessment/evaluate_ragas.py --generate-only

python eval/case_assessment/evaluate_ragas.py \
  --dataset eval/case_assessment/results/live_retrieval/dataset.completed.json \
  --provider mistral
```

Nếu dùng OpenAI để chấm, đặt `OPENAI_API_KEY` và thay bằng `--provider openai --judge-model TEN_MODEL`. Phần RAG vẫn dùng cấu hình Mistral của ứng dụng.

### Dùng Gemini làm LLM-as-judge

Đặt `GOOGLE_API_KEY` trong `.env` bằng khóa Gemini Developer API từ Google AI Studio.
Có thể dùng `GEMINI_API_KEY` thay thế; nếu đặt cả hai, `GOOGLE_API_KEY` được ưu tiên.
Thư viện `langchain-google-genai` đã có trong `requirements.txt` của bộ đánh giá.
Không cần sửa `MODEL_NAME`: ứng dụng vẫn dùng Mistral để embedding và tạo assessment.

```bash
python eval/case_assessment/evaluate_ragas.py \
  --dataset eval/case_assessment/results/live_retrieval/dataset.completed.json \
  --generate-missing \
  --provider gemini \
  --judge-model TEN_MODEL_GEMINI \
  --output-dir eval/case_assessment/results/gemini_judge
```

Thay `TEN_MODEL_GEMINI` bằng ID model Gemini mà tài khoản được phép dùng. Nếu dataset
đã đầy đủ, bỏ `--generate-missing` để chỉ chấm các assessment đã lưu. Có thể đặt
`RAGAS_JUDGE_MODEL` trong `.env` thay cho `--judge-model`; provider Gemini không dùng
`MODEL_NAME` của Mistral làm model chấm. Mặc định chấm cả 4 chỉ số.

Khi tiếp tục từ checkpoint ở thư mục khác và còn thiếu output, provenance của các
case đã có được xem là output đã thu thập (`captured_outputs`); dữ liệu thực đã lưu
vẫn được giữ. Dùng cùng thư mục capture để giữ nguyên provenance cho toàn bộ lần chạy.

Client dùng Gemini Developer API (`vertexai=False`), không tự chuyển sang Vertex AI.
Timeout và số lần thử lại được giới hạn như các judge khác. Gemini 3 dùng temperature
1.0 theo khuyến nghị của Google; các model khác dùng 0. Không bật công cụ tìm kiếm
web cho judge. API key không được ghi vào các tệp kết quả.

Tài liệu tích hợp: [LangChain ChatGoogleGenerativeAI](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai).

### Dùng OpenRouter làm LLM-as-judge

Đặt `OPENROUTER_API_KEY` trong `.env`. Dùng `--provider openrouter` và
`--judge-model` là ID chính xác của model trong catalog OpenRouter (thường có dạng
`provider/model`). Có thể dùng `RAGAS_JUDGE_MODEL` thay cho `--judge-model`.
Không cần `OPENAI_API_KEY` hay thư viện mới: client dùng `langchain-openai` đã có
trong dependency, với endpoint cố định `https://openrouter.ai/api/v1`.

```bash
python eval/case_assessment/evaluate_ragas.py \
  --dataset eval/case_assessment/results/live_retrieval/dataset.completed.json \
  --provider openrouter \
  --judge-model PROVIDER/MODEL \
  --output-dir eval/case_assessment/results/openrouter_judge
```

Thay `PROVIDER/MODEL` bằng model ID được tài khoản của bạn phép truy cập. Nếu dataset
còn thiếu output, thêm `--generate-missing`; phần retrieval và assessment vẫn dùng
Mistral của ứng dụng. Nếu output đã đủ, chỉ gọi judge để chấm cả 4 metric. Khi đổi
judge/provider, lưu ở thư mục kết quả mới để tách biệt các lần chạy.

Client gọi API chat completions với timeout và số lần retry có giới hạn, giữ sampling
mặc định của model. Khóa OpenRouter không được lưu vào báo cáo hoặc dataset. Việc đi
qua OpenRouter không bảo đảm model luôn có sẵn; lỗi provider vẫn tạo điểm `null`.

Tài liệu: [OpenRouter quickstart](https://openrouter.ai/docs/quickstart).

## 4. Đọc kết quả

Mặc định kết quả nằm trong `eval/case_assessment/results/live_retrieval/`:

| File | Nội dung |
| --- | --- |
| `report.md` | Báo cáo tổng hợp |
| `scores.csv`, `scores.json` | Điểm từng vụ việc |
| `summary.json` | Điểm trung bình, cấu hình và lỗi |
| `dataset.completed.json` | Câu trả lời và các đoạn thực sự truy xuất được |
| `generated_runs.json` | Chi tiết truy xuất, ID đoạn, điểm và kết quả đánh giá |
| `validation.json` | Kết quả kiểm tra cấu trúc dataset |

| Chỉ số | Ý nghĩa |
| --- | --- |
| `faithfulness` | Câu trả lời có căn cứ từ đoạn truy xuất và tình tiết đầu vào không? |
| `factual_correctness` | Câu trả lời khớp các nhận định trong đáp án tham chiếu đến đâu? |
| `context_precision` | Các đoạn liên quan có được xếp trước các đoạn không liên quan không? |
| `context_recall` | Truy xuất có bao phủ chứng cứ tham chiếu không? |

Điểm lỗi API/chấm được lưu là `null`, không phải `0`. Xem lỗi trong `summary.json`. Đáp án tham chiếu hiện là bản nháp cần chuyên gia HR/pháp chế rà soát.

## Chạy tiếp và cập nhật dataset

- Khi bị gián đoạn: dùng `dataset.completed.json` với `--generate-missing` và cùng `--output-dir` để tiếp tục các mẫu còn thiếu.
- Thêm `--resume` để dùng lại chỉ số đã chấm đủ khi dataset và cấu hình không đổi.
- Khi đổi corpus hoặc model chấm: dùng thư mục kết quả mới và tạo lại đầu ra RAG từ dataset gốc.
- `build_dataset.py` đọc `policy_snapshot.json` và DOCX trong `tested_golden_dataset/`; không tự cập nhật snapshot từ database. Script ghi đè `ragas_dataset.json` và `source_metadata.json`, nên lưu các chỉnh sửa đã được duyệt trước khi chạy.
