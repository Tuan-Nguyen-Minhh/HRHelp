# VERIFY DB — MANUAL SIGN-OFF (V5-manual)

_Ngày: 2026-09-27. Plan: `data_pipeline_steps/step4_5_plan.md` REV.2 mục 4._
_Ngoài auto-loop: auto-loop V1–V4ter/V5-auto/V6–V7 không chờ bước này để PASS,
nhưng **nghiệm cuối yêu cầu cả hai**._

## 1. Trạng thái

| | |
|---|---|
| Auto-loop (`verify_db.py`) | 70 PASS / 0 FAIL (`verify_db_009.log`) |
| Manual review (file này) | ☐ **CHƯA KÝ** |
| Negative control (`mutation_test.py`) | 18/18 mutation bị bắt (`mutation_test_005.log`) |

## 2. Quy ước lấy mẫu

- Seed cố định `42` để tái lập.
- Mỗi rule type lấy **5–10%** (tính bẛc nhất, tối thiểu 1).
- Mẫu được materialize thành SQL ở mục 4 để reviewer chạy lại được, không tự chọn
  mẫu khác.

## 3. Ngân hàng mẫu theo rule type

Số liệu lấy từ DB hiện tại (565 refs).

| # | rule type | tổng | mẫu 5–10% | số mẫu | đã duyệt | ghi chú |
|---|---|---|---|---|---|---|
| 1 | EXPLICIT_SELF | 253 | 13–25 | 20 | ☐ | |
| 2 | EXPLICIT | 191 | 10–19 | 15 | ☐ | |
| 3 | DEFAULT_SELF | 72 | 4–7 | 5 | ☐ | |
| 4 | SCOPED_CHAPEAU | 25 | 1–2 | 2 | ☐ | |
| 5 | LIST_EXPANSION | 18 | 1–2 | 2 | ☐ | |
| 6 | QUOTED_EXTERNAL | 3 | 1 | 1 | ☐ | |
| 7 | BOUNDARY_CHECK | 3 | 1 | 1 | ☐ | |

Tổng mẫu đề xuất: **46 / 565 = 8,1%**.

## 4. Checklist từng mẫu

Với mỗi dòng mẫu, kiểm tra bằng mắt:

- [ ] `target_doc` có đúng là văn bản được dẫn trong câu chữ (không nhầm Điều này
      nhận qualifier của Điều khác)
- [ ] `article` đúng; `clause` / `point` đúng nếu có
- [ ] `target_chunk_id`:
  - luật **ngoài** bộ 3 → phải `NULL`
  - trong bộ 3 → chunk **thuộc đúng Điều**, và mức granularity hợp lý
    (xem bảng phân bố resolve bên dưới)
- [ ] `confidence` / `rule` khớp với cách câu chữ thực tế
- [ ] `needs_review` / `needs_reason` đúng

### Phân bố resolve cần nắm khi duyệt

| cách resolve | số refs | kỳ vọng khi đọc |
|---|---|---|
| `point` | 19 | chunk cấp điểm |
| `clause` | 186 | chunk cấp khoản |
| `article` | 192 | chunk cấp Điều |
| `fallback` | 108 | chunk đại diện Điều (điểm/khoản không tồn tại ở bản hợp nhất) |
| `external` | 60 | `target_chunk_id IS NULL` |

**108 ca `fallback` là điểm cần soi kỹ nhất.** Đây là các ref mà điểm/khoản được dẫn
không tồn tại trong bản hợp nhất 2019, hoặc Điều đã bị tách hết thành khoản nên không
còn chunk cấp Điều. Ví dụ đã biết: NĐ145 → BLLD Điều 54 khoản 3 (Đ54 hợp nhất chỉ có
khoản 1–2); NĐ145 → BLLD Điều 122 điểm c (Đ122 không có chunk điểm).

Nếu reviewer cho rằng một ca `fallback` **không nên** được neo, thì đó là phát hiện
cần ghi lại và xử lý ở B5 (chỉ chạy lại từ B5, không đụng model/migration B4).

## 5. Truy vấn lấy mẫu (tái lập được)

```sql
-- Ví dụ: 20 mẫu EXPLICIT_SELF
SELECT r.source_chunk_id, r.target_doc, r.article, r.clause, r.point,
       r.rule, r.confidence, r.target_chunk_id, r.needs_review, r.needs_reason,
       left(t.text, 120) AS target_text
FROM legal_chunk_references r
LEFT JOIN legal_chunks t ON t.chunk_id = r.target_chunk_id
WHERE r.rule = 'EXPLICIT_SELF'
ORDER BY r.ref_id
LIMIT 20;
```

```sql
-- 108 ca fallback: chunk cấp Điều nhưng ref mang granularity không resolve được
SELECT r.source_chunk_id, r.target_doc, r.article, r.clause, r.point, r.rule
FROM legal_chunk_references r
WHERE r.target_chunk_id IS NOT NULL
  AND r.target_doc IN ('18/VBHN-VPQH','145/2020/NĐ-CP','283/2026/NĐ-CP')
  AND (
        (r.point IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM legal_chunks c WHERE c.document_id=r.target_doc
              AND c.article_number=r.article AND c.clause_number=r.clause
              AND c.point_letter=lower(r.point) AND c.chunk_level='POINT'))
     OR (r.point IS NULL AND r.clause IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM legal_chunks c WHERE c.document_id=r.target_doc
              AND c.article_number=r.article AND c.clause_number=r.clause
              AND c.chunk_level='CLAUSE'))
        )
ORDER BY r.ref_id;
```

## 6. Kết luận

- [ ] 46/46 mẫu đúng
- [ ] 108 ca `fallback` đã được soi, chấp nhận hoặc ghi nhận ngoại lệ
- [ ] `BOUNDARY = 3`, `UNRESOLVED = 0` đã đối chiếu tay
- [ ] Không phát hiện lỗi mới

## 7. Ký

| Vai trò | Họ tên | Ngày | Chữ ký |
|---|---|---|---|
| Reviewer | | | |
| Approver | | | |

> Nghiệm cuối B4+B5 **chưa được cấp** cho tới khi mục 7 có đủ 2 chữ ký.
