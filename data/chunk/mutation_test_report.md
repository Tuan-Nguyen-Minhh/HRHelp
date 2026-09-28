# Mutation test — bằng chứng verify V1–V7 không phải check rỗng

_Ngày: 2026-09-27. Script: `scripts/mutation_test.py`. Log: `mutation_test_001.log`
… `mutation_test_003.log`._

## 1. Vì sao cần

Một danh sách check toàn `[PASS]` không chứng minh gì: nếu check sai cú pháp so sánh,
hoặc so sánh nhầm cột, nó vẫn PASS. Cách kiểm chứng duy nhất là **phá dữ liệu có chủ
đích** rồi đòi đúng check phải FAIL.

## 2. Cách chạy

```bash
python scripts/mutation_test.py
```

Mỗi mutation: áp dụng → chạy `verify_db.py` đầy đủ → đòi check tương ứng xuất hiện
trong danh sách FAIL → khôi phục bằng cách chạy lại seed. Cuối cùng xác nhận DB sạch
và file nguồn khôi phục **byte-exact**.

> Cảnh báo: script ghi vào database và sửa tạm một file JSON nguồn. Chạy trên DB
> disposable. Script tự khôi phục và tự assert lại ở cuối.

## 3. Kết quả — 18/18 mutation bị bắt

| # | Mutation | Check phải FAIL | Kết quả |
|---|---|---|---|
| 1 | `alembic_version` → revision giả | `V1.alembic_current_eq_head` | CAUGHT |
| 2 | `legal_documents.chunk_count` nói dối (999) | `V2.BLLD.chunk_count_cross` | CAUGHT |
| 3 | `amended_by` thành JSON `null` thay vì SQL NULL | `V2.amended_by_is_object_or_null` | CAUGHT |
| 4 | `amended_by` thành `{}` ở nơi phải là SQL NULL | `V2.ND283_2026.amended_by_sql_null` | CAUGHT |
| 5 | xoá 1 chunk BLLD | `V3.BLLD.count` | CAUGHT |
| 4 | sửa `meta.has_chapeau` của chunk **có trong sample** | `V3-bis.special_columns` | CAUGHT |
| 5 | xoá `is_quoted_external_text` toàn bộ | `V3-bis.quoted_external_count` | CAUGHT |
| 6 | gắn parent treo cho chunk đang có parent NULL | `V3-ter.dangling_parent` | CAUGHT |
| 7 | xoá parent của chunk đang có parent treo | `V3-ter.dangling_parent` | CAUGHT |
| 8 | xoá 1 dòng `legal_chunk_references` | `V4.BLLD.count` | CAUGHT |
| 9 | trỏ ref tới Điều không tồn tại | `V4.internal_article_exists` | CAUGHT |
| 10 | phá vỡ `needs_review` ↔ `needs_reason` | `V4.needs_review_consistent` | CAUGHT |
| 11 | gắn cờ UNRESOLVED cho 1 ref | `V4-bis.unresolved` | CAUGHT |
| 12 | xoá hết cờ BOUNDARY | `V4-ter.boundary` | CAUGHT |
| 13 | cho ref luật **ngoài** một `target_chunk_id` khác NULL | `V5.1_ND283_A044C01_to_BHXH_D28` | CAUGHT |
| 14 | xoá 1 ref inbound tới BLLD Đ169 | `V5.2_BLLD_D169_inbound_from_ND145` | CAUGHT |
| 15 | xoá ref LIST_EXPANSION tới Đ14 của A066 | `V5.5_ND283_A066_LIST_self_D7_D14` | CAUGHT |
| 16 | hỏng file JSON nguồn (hỏng từ trước lần chạy) | `V7.matches_pinned_manifest` | CAUGHT |

Nhiều mutation bị **nhiều check cùng** bắt (ví dụ #3 → V2, V3, V6 đều FAIL), đúng như
mong đợi vì các check này cùng suy ra từ một nguồn sự thật.

## 4. Các lần "MISSED" dẫn tới sửa code / sửa tooling thật

Không phải mọi lần "MISSED" đều là mutation sai. Ba lần chạy đầu đều không đạt, và
điều tra ra **hai vấn đề thật**:

### 4.1 V7 — lỗi thiết kế thật của check

V7 ban đầu chỉ so sha256 *trong một lần chạy* (`before` lúc bắt đầu vs `after` lúc
cuối). Nhưng file nguồn bị hỏng **trước** lần chạy đó thì `before` và `after` giống
nhau → **PASS**. Tức V7 không thể phát hiện hư hỏng sẵn có, chỉ phát hiện hư hỏng do
chính seed gây ra trong lúc chạy. Mutation 16 chứng minh: thêm một dòng trắng vào
`chunks_BLLD.json` (JSON vẫn parse được, nội dung không đổi) và verify vẫn PASS.

**Cách sửa:** thêm `data/chunk/source_manifest.json` ghim sha256 của 6 file nguồn đã
đóng băng. V7 nay assert khớp manifest, và manifest thiếu thì FAIL. Cập nhật có chủ
đích bằng `python scripts/verify_db.py --write-manifest`.

### 4.2 Mutation test tự làm hỏng file nguồn — lỗi trong tooling

Bản mutation test đầu tiên khôi phục file nguồn bằng
`path.write_text(original_text, encoding="utf-8")`. Trên Windows, `write_text` mở
file ở text mode với `newline=None`, nên **mọi `\n` bị dịch thành `\r\n`**. File
743 KB bị viết lại toàn bộ 13 761 dòng, sha256 đổi, V7 báo FAIL — tức chính mutation
test đã phá dữ liệu mà nó sinh ra để kiểm tra.

Phát hiện nhờ dòng tự kiểm ở cuối script (`source file restored byte-exact: False`).
Đã sửa bằng `write_bytes` và khôi phục file về đúng byte gốc, xác nhận sha256 khớp
manifest `79a7586e7d1800455c4a58896979a2c517ee66842f2c39d21650d04ff2ca2d28`.

Bài học: script kiểm thử **phải tự assert trạng thái sau khi khôi phục**, nếu không
thì chính nó là nguồn hư hỏng.

### 4.3 V3-bis — mutation sai, không phải bug

Mutation đầu tiên sửa `meta` của `BLLD:CI:M00:A003:C01`, chunk **không** nằm trong
sample 30 ID của V3-bis. Đây đúng là thiết kế của plan: V3-bis là spot check 30
chunk với seed cố định, in đủ 30 ID để tái lập — không soi 1289 chunk. Sau khi chọn
đúng chunk trong sample (`BLLD:CX:M00:A139:C04`, vị trí 1), mutation bị bắt ngay.

### 4.4 V3-ter — mutation sai, không phải bug

Mutation thêm `parent_chunk_id='NOPE:...'` cho `BLLD:CI:M00:A003:C01`, nhưng chunk đó
vốn đã có parent là `BLLD:CI:M00:A003` — mà article id này **không tồn tại** trong
bảng `legal_chunks` (Điều 3 bị tách hết thành khoản). Nên nó đã treo sẵn, thêm parent treo
nữa thì count không đổi.

Kiểm tra sâu hơn cho thấy: **toàn bộ 1030 `parent_chunk_id` non-null đều treo, 0
chunk nào có parent resolve được**; 259 chunk còn lại có `parent_chunk_id IS NULL`.
Đây là đặc tính đã biết của thiết kế gốc (`chunking_engine._make_chunk` luôn trỏ về
article id), đã ghi ở `CHANGELOG.md` mục "Phụ lục". Để mutation có tác dụng, phải
chọn chunk đang có parent NULL để gắn parent mới, hoặc xoá parent của một chunk đang
treo — cả hai đều bị bắt (mục 3 #6, #7).

### 4.5 Sai tên check trong chính harness (lần chạy 003)

Mutation #4 nhắm `legal_documents.document_id = '283/2026/NĐ-CP'` nhưng lại viết kỳ vọng
là `V2.ND145_2020.amended_by_sql_null`. Chạy tay để kiểm: mutation có hiệu lực
(rowcount = 1) và verify **thực sự** báo FAIL — nhưng tên check thật là
`V2.ND283_2026.amended_by_sql_null`. Tức là **check bắt đúng, harness của tôi khai
báo sai**. Đã sửa tên kỳ vọng.

Đáng chú ý: cùng lúc đó tôi cũng nghi ngờ `Đ` trong `NĐ-CP` bị sai codepoint
(U+0110 vs U+0111 trông giống nhau). Đã kiểm byte: `document_id` trong DB là
`4ec490` và literal trong script cũng `4ec490` — **không có vấn đề encoding**. Đã loại
bỏ giả thuyết này thay vì sửa mò.

## 5. Kết luận

- 18/18 mutation bị bắt.
- Lỗi `amended_by` là JSON `null` chứ không phải SQL NULL được phát hiện khi rà
  trạng thái cuối, đã sửa ở model + seed và thêm 3 check V2 + 2 mutation.
- Một lỗi thiết kế thật của V7 được phát hiện và sửa nhờ mutation test.
- Một lỗi trong chính tooling kiểm thử (CRLF) được phát hiện nhờ dòng tự assert.
- Hai lần "MISSED" còn lại là mutation sai, đã ghi lại để không tái diễn.
