# Giới thiệu Dữ liệu

Thư mục này chứa các tài liệu ở hai định dạng: bản gốc (`.docx`) và bản đã được chuyển đổi sang định dạng Markdown (`.md`).

## Danh sách tài liệu

Dưới đây là danh sách các văn bản luật có trong thư mục, bao gồm cả bản gốc và bản Markdown:

| Tên tệp (không đuôi) | Định dạng | Nội dung văn bản luật |
| --- | --- | --- |
| `2026_131_18_VBHN-VPQH` | `.docx`, `.md` | **Bộ luật Lao động** (Văn bản hợp nhất số 18/VBHN-VPQH). |
| `283_2026_ND-CP_642116` | `.docx`, `.md` | **Nghị định 283/2026/NĐ-CP**: Quy định xử phạt vi phạm hành chính trong lĩnh vực lao động, bảo hiểm xã hội, người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng. |
| `nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong` | `.docx`, `.md` | **Nghị định 145/2020/NĐ-CP**: Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về điều kiện lao động và quan hệ lao động. |

## Danh sách văn bản nội bộ

| Tên tệp (không đuôi) | Loại | Nội dung |
| --- | --- | --- |
| `noi_quy_mau_cong_ty` | `NOI_QUY` | **Nội quy lao động** của Công ty (số hiệu `NQLD-HRCORP-2026`) — xem mục "Văn bản nội bộ trong corpus" bên dưới. |

Cả 4 văn bản (3 luật + 1 nội quy) đều đi qua cùng một pipeline
step2 → step3 → seed → embed.

## Cấu trúc thư mục

* **`raw/`**: Chứa các tệp tài liệu văn bản gốc ở định dạng Word (`.docx`).
* **`markdown/`**: Chứa các tệp văn bản đã được trích xuất và chuyển đổi sang định dạng Markdown tương ứng (`.md`) bằng MarkItDown (giữ nguyên lỗi spacing/heading gốc để step2 sửa).
* **`cleaned_markdown/`**: Output bước 2 — `.md` đã sửa footnote dính, khoản dính (`2.X`), heading-merge (BLLD 220 / NĐ145 115 / NĐ283 68 Điều) + `metadata_summary.json`.
* **`chunk/`**: Output bước 3 (chunk là data) — `document_tree_*.json` (cây Chương→Mục→Điều trung gian), `chunks_*.json` (BLLD 381 / NĐ145 377 / NĐ283 531 / NQCT 88, tổng 1377), `step3_stats.json`, `validation_report.md` (per-doc, **tự liệt kê mọi `chunks_*.json`** nên văn bản mới không bị bỏ sót), `low_confidence_refs.json`, `references_sample_review.md/.csv`, `CHANGELOG.md`, `verify_final.log`.

> Số chunk không gõ tay ở đây và trong `scripts/`. Chạy
> `python scripts/corpus_expectations.py` để in số đúng tính từ
> `data/chunk/chunks_*.json` — cùng nguồn mà `embed_legal.py` dùng.

## Văn bản nội bộ trong corpus

| Mã | `document_id` | Loại | Nội dung |
| --- | --- | --- | --- |
| `NQCT` | `NQLD-HRCORP-2026` | `NOI_QUY` / `VAN_BAN_NOI_BO` | **Nội quy lao động** — 82 Điều / 21 Chương |

Nội quy gồm hai phần:

1. **Chương I–XI** — quy định nền: thời giờ làm việc, nghỉ phép, trật tự,
   an toàn vệ sinh lao động, ứng phó sự cố, bảo mật CNTT, đánh giá và đào tạo.
2. **Chương XII–XXI** — các **họ quy trình** (Điều 46–82), bổ sung 2026-10-03
   từ mẫu nội quy sản xuất / dịch vụ / xây dựng / TNHH:
   khiếu nại nội bộ (lần 1 / lần 2 / tranh chấp / đối thoại với tổ chức đại
   diện), phản ánh của khách hàng, văn bản nội bộ & phát ngôn, mua sắm &
   quản lý tài sản, tiếp nhận – bàn giao – chấm dứt HĐLĐ, đào tạo & thưởng,
   nghiệm thu chất lượng, báo cáo sự cố & điều tra tai nạn, họp & báo cáo nội bộ.

Mọi hình thức xử lý kỷ luật trong nội quy đều bám đúng **Điều 124 Bộ luật
Lao động** (4 hình thức: khiển trách, kéo dài thời hạn nâng lương không quá
06 tháng, cách chức, sa thải). Nội quy **không** dùng "bản kiểm điểm", phạt
tiền hay trừ lương thay cho kỷ luật — các hình thức đó không phải kỷ luật
lao động theo pháp luật.

> **Lưu ý khi chạy step2.** `noi_quy_mau_cong_ty.md` **không** phải output của
> MarkItDown mà là văn bản nội bộ viết tay, nên nó có **không có** file `.docx`
> trong `data/raw/` và tiêu đề nó dùng `- **Số hiệu:** ...` thay vì `Số: ...`.
> Vì vậy `extract_metadata` của step2 **không** đọc được `document_number` /
> `document_form` từ file này (ghi `null` / `VĂN BẢN GỐC`) và nếu chạy step2
> nó còn ghi đè header trong `.md`. Nguồn chuẩn cho danh tính văn bản là
> `DOC_ID_MAP` (`hierarchy_parser.py`) — đó cũng là thứ step3 và `seed_legal.py`
> thực sự dùng. Muốn sửa nội quy: sửa `data/cleaned_markdown/` rồi chạy
> `run_step3` (bỏ qua step2 cho riêng văn bản này). Ba văn bản luật thì vẫn
> chạy step2 bình thường.

## Pipeline regenerate

```bash
python -m data_pipeline_steps.step2.step2_preprocessing  # markdown → cleaned_markdown
python -m data_pipeline_steps.step3.run_step3            # cleaned → data/processed
python -m data_pipeline_steps.step3.validate_step3       # audit per-doc
```

## Phương pháp chuyển đổi

Toàn bộ các tệp Word trong thư mục `raw` được chuyển đổi tự động sang thư mục `markdown` bằng công cụ **MarkItDown** do Microsoft phát triển. MarkItDown giúp trích xuất nội dung từ các tài liệu Office (như `.docx`) một cách nhanh chóng và giữ lại cấu trúc văn bản một cách tối ưu dưới định dạng Markdown.
