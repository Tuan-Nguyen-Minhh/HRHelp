# Giới thiệu Dữ liệu

Thư mục này chứa các tài liệu ở hai định dạng: bản gốc (`.docx`) và bản đã được chuyển đổi sang định dạng Markdown (`.md`).

## Danh sách tài liệu

Dưới đây là danh sách các văn bản luật có trong thư mục, bao gồm cả bản gốc và bản Markdown:

| Tên tệp (không đuôi) | Định dạng | Nội dung văn bản luật |
| --- | --- | --- |
| `2026_131_18_VBHN-VPQH` | `.docx`, `.md` | **Bộ luật Lao động** (Văn bản hợp nhất số 18/VBHN-VPQH). |
| `283_2026_ND-CP_642116` | `.docx`, `.md` | **Nghị định 283/2026/NĐ-CP**: Quy định xử phạt vi phạm hành chính trong lĩnh vực lao động, bảo hiểm xã hội, người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng. |
| `nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong` | `.docx`, `.md` | **Nghị định 145/2020/NĐ-CP**: Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về điều kiện lao động và quan hệ lao động. |

## Cấu trúc thư mục

* **`raw/`**: Chứa các tệp tài liệu văn bản gốc ở định dạng Word (`.docx`).
* **`markdown/`**: Chứa các tệp văn bản đã được trích xuất và chuyển đổi sang định dạng Markdown tương ứng (`.md`) bằng MarkItDown (giữ nguyên lỗi spacing/heading gốc để step2 sửa).
* **`cleaned_markdown/`**: Output bước 2 — `.md` đã sửa footnote dính, khoản dính (`2.X`), heading-merge (BLLD 220 / NĐ145 115 / NĐ283 68 Điều) + `metadata_summary.json`.
* **`chunk/`**: Output bước 3 (chunk là data) — `document_tree_*.json` (cây Chương→Mục→Điều trung gian), `chunks_*.json` (BLLD 381 / NĐ145 377 / NĐ283 531, tổng 1289), `step3_stats.json`, `validation_report.md` (per-doc), `low_confidence_refs.json`, `references_sample_review.md/.csv`, `CHANGELOG.md`, `verify_final.log`.

## Pipeline regenerate

```bash
python -m data_pipeline_steps.step2.step2_preprocessing  # markdown → cleaned_markdown
python -m data_pipeline_steps.step3.run_step3            # cleaned → data/processed
python -m data_pipeline_steps.step3.validate_step3       # audit per-doc
```

## Phương pháp chuyển đổi

Toàn bộ các tệp Word trong thư mục `raw` được chuyển đổi tự động sang thư mục `markdown` bằng công cụ **MarkItDown** do Microsoft phát triển. MarkItDown giúp trích xuất nội dung từ các tài liệu Office (như `.docx`) một cách nhanh chóng và giữ lại cấu trúc văn bản một cách tối ưu dưới định dạng Markdown.
