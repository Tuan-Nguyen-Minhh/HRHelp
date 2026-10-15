# Đánh giá retrieval có nhãn chuyên gia

Công cụ này đo candidate recall, final recall/precision, nDCG và tỷ lệ giữ đủ một bộ căn cứ chấp nhận được. Nó không tự xác nhận mức kỷ luật đúng pháp luật. Bộ nhãn phải được HR/pháp chế duyệt; công cụ từ chối `reference_status` khác `expert_reviewed`.

Reference là JSON array. Mỗi case gồm `case_id`, `reference_status`, `incident_date`, `description`, `family`, `facts`, `evidence_bundles` (một hoặc nhiều danh sách UUID chunk của các phương án đủ căn cứ), `critical_chunk_ids`, và tùy chọn `relevance` (chunk UUID → mức 0–3). Đối chiếu UUID/nội dung/phiên bản trong database trước khi chấm. Chưa có bộ nhãn chuyên gia mới được tạo tự động.

Validate cấu trúc, không gọi API:

```bash
.venv/bin/python -m eval.retrieval.evaluate --references PATH_TO_REVIEWED_JSON --validate-only
```

Chạy retrieval với database hiện tại, Mistral embeddings và Cohere; có phát sinh phí API:

```bash
.venv/bin/python -m eval.retrieval.evaluate --references PATH_TO_REVIEWED_JSON --generate --output-dir eval/retrieval/results/cohere_pro
```

Chấm lại kết quả đã capture, không gọi database/API:

```bash
.venv/bin/python -m eval.retrieval.evaluate --references PATH_TO_REVIEWED_JSON --runs eval/retrieval/results/cohere_pro/runs.json --output-dir eval/retrieval/results/cohere_pro
```

Giữ nguyên corpus, model synthesis và tập test khi so sánh cấu hình retrieval. Báo kết quả theo từng case, mẫu số và các gap; không dùng điểm trung bình tốt để che một case mất ngoại lệ quan trọng. Đo mức đề xuất và lý do dừng riêng ở eval assessment, với đáp án được chuyên gia xác nhận.
