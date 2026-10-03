# CHANGELOG — Mở rộng NQCT (nội quy lao động): 18 → 82 Điều, thêm 10 họ quy trình

_Ngày: 2026-10-03. Nhánh `tuan_data_pipeline`. Phạm vi: chỉ văn bản nội bộ
`NQCT` (`NQLD-HRCORP-2026`) + hạ tầng đếm số. Ba văn bản luật
(BLLD `18/VBHN-VPQH`, NĐ 145/2020, NĐ 283/2026) **không đổi byte nào**._

## 1. Vấn đề

Corpus chỉ có **45 Điều** nội quy và tập trung nặng vào kỷ luật lao động
(Chương V, VI, VIII chiếm 19/45 Điều). Các quy trình vận hành thường ngày —
khiếu nại nội bộ, phản ánh khách hàng, văn bản nội bộ, mua sắm & tài sản,
onboarding/offboarding, nghiệm thu, điều tra tai nạn, đối thoại — **không có
mặt**. Đây đúng là loại nội dung agent cần để trả lời "quy trình này làm thế
nào, ai làm, bao lâu, ai duyệt".

## 2. Nguồn

5 mẫu thu thập (`quy định nội bộ công ty mẫu/`): nội quy công ty **sản xuất**,
**dịch vụ**, **xây dựng**, **TNHH** (EasyHRM) + **mẫu quy chế quản trị công ty**
(Luật Doanh nghiệp 2020 — HĐQT/ĐHĐC/BKS/GĐ).

Đọc hết 5 mẫu, gom các *họ quy trình* có thể dùng cho một doanh nghiệp lao động
nói chung, viết lại theo văn phong quy định của NQCT sẵn có (đánh số Điều liên
tục, cấu trúc `khoản` / `điểm`, header `## Chương` + `#### Điều` để step3 parse
được).

## 3. Đã thêm — Chương XII–XXI (Điều 46–82, +37 Điều)

| Chương | Điều | Họ quy trình | Gốc |
| --- | --- | --- | --- |
| XII | 46–52 | Khiếu nại nội bộ: nguyên tắc, tiếp nhận (5 bước), phân cấp thẩm quyền, khiếu nại lần 1 (30 ngày), lần 2 (45 ngày), tranh chấp cá nhân + hòa giải, tham vấn tổ chức đại diện NLĐ | TNHH/Dịch vụ + BLLĐ 131, 187–190 |
| XIII | 53–56 | Phản ánh khách hàng: nguyên tắc, phân loại A/B/C theo SLA (24 giờ → 3 ngày), quy trình 6 bước, quản lý dữ liệu khách hàng | Dịch vụ |
| XIV | 57–60 | Văn bản nội bộ: soạn–phản biện–ký–phát hành–lưu (5 bước), đối chiếu & công bố, phát ngôn ra ngoài | Quy chế quản trị (mục họp, biên bản, nghị quyết) |
| XV | 61–63 | Mua sắm theo ngưỡng giá trị (5 triệu / 50 triệu / 500 triệu), cấp phát tài sản (4 bước), mượn–trả–thanh lý (5 bước) | Sản xuất ("đổi cũ lấy mới", sổ mượn) |
| XVI | 64–67 | Onboarding (4 bước), bàn giao offboarding (4 bước), chấm dứt HĐLĐ, thanh toán lương & quyền lợi | BLLĐ 24/25/34/35/45/48/113 |
| XVII | 68–70 | Đào tạo (đề xuất → duyệt → tổ chức → đánh giá), hướng dẫn nhân viên mới, thưởng & ghi nhận kết quả | BLLĐ 104 |
| XVIII | 71–73 | Tự kiểm soát trước bàn giao, nghiệm thu & kiểm soát chất lượng, vận hành thiết bị có chứng chỉ | Xây dựng (nghiệm thu, gian lận hồ sơ) |
| XIX | 74–76 | Báo cáo sự cố & gần như sự cố (4 bước), lập biên bản + hội đồng điều tra tai nạn (4 bước), kiến nghị sau điều tra | Xây dựng/Sản xuất |
| XX | 77–80 | Họp nội bộ, lập & lưu biên bản họp, báo cáo công việc định kỳ, đối thoại định kỳ (≥ 6 tháng/lần) | Quy chế quản trị + ND145 Đ38 |
| XXI | 81–82 | Hiệu lực thi hành, tổ chức thực hiện & sửa đổi | Cả 5 mẫu (Điều 22/23 gần như giống nhau) |

**Không** thêm hệ quản trị cổ phần (ĐHĐC/HĐQT/BKS/GĐ) làm văn bản thứ 5: mẫu đó là
checklist rỗng về nội dung ("bao gồm các nội dung chính sau đây"), lệch hẳn phạm
vi agent (VPHC lao động) và chỉ vài chunk có thông tin dùng được. Phần hữu ích
(họp, biểu quyết, biên bản, phê duyệt) đã được lấy vào Chương XIV và XX.

## 4. Ràng buộc pháp lý — đã kiểm tra từng trích dẫn

Yêu cầu: đa dạng hoá nhưng **không** vẽ ra hướng sai pháp luật. Cụ thể:

- **Không** đưa "bản kiểm điểm" (BKĐ) / phạt tiền / trừ lương vào corpus dù
  mẫu sản xuất dùng BKĐ rất nhiều. Cả 4 hình thức xử lý kỷ luật trong NQCT vẫn
  bám đúng **Điều 124 BLLD**; Điều 10 của nội quy đã ghi rõ *"Tuyệt đối không áp
  dụng hình thức phạt tiền, trừ lương thay cho việc xử lý kỷ luật lao động."*
  BKĐ **không phải** hình thức kỷ luật lao động, nên đưa vào chỉ dạy model điều
  sai.
- **Sửa 7 chỗ sai pháp luật / sai trích dẫn**, phát hiện khi đối chiếu từng câu với
  text thật trong `chunks_BLLD.json` (số Điều trong corpus này đã bị đánh lại so
  với BLLD 2019 — ví dụ Điều 185 là *"Hội đồng trọng tài lao động"* chứ không phải
  hội đồng điều tra tai nạn lao động):

  | Nội dung | Sai | Đúng | Nguồn |
  | --- | --- | --- | --- |
  | Hội đồng điều tra tai nạn lao động | trích Điều 185 | bỏ trích, mô tả là cơ chế nội bộ + trích **Điều 122** (biên bản bắt buộc khi xử lý kỷ luật) | Điều 185 = HĐTT |
  | Thời hiệu khiếu nại lần 1 / lần 2 | "trừ trường hợp khoản 2 Điều 189" | bỏ ngoại lệ, quá hạn thì sang tranh chấp theo Điều 51 | Điều 189 là giải quyết tranh chấp của HĐTT |
  | Rà soát văn bản với HĐLĐ | trích Điều 28 | **Điều 21** (Nội dung hợp đồng lao động) | Điều 28 = Thực hiện công việc theo HĐLĐ |
  | Điều 50 khoản 4 | trích Điều 192 | bỏ trích | Điều 192 = tranh chấp **tập thể về quyền**, sai bản chất với khiếu nại cá nhân |
  | Thời hạn hòa giải | "15 ngày làm việc" | **05 ngày làm việc** | Điều 188 khoản 2 |
  | Thời hiệu tranh chấp cá nhân | gộp thành "01 năm" | **3 mức**: hòa giải 06 tháng · HĐTT 09 tháng · Tòa án 01 năm, tính từ ngày phát hiện hành vi | Điều 190 khoản 1, 2, 3 |
  | Thời hạn thanh toán khi chấm dứt HĐLĐ | "trừ trường hợp cả hai bên thỏa thuận khác" | **kéo dài được nhưng không quá 30 ngày** trong 4 trường hợp luật định (NSDLĐ chấm dứt hoạt động; thay đổi cơ cấu/công nghệ/vì lý do kinh tế; chia tách nhập sáp nhập / chuyển nhượng; thiên tai hỏa hoạn dịch bệnh) | Điều 48 khoản 1 |
  | Đăng ký nội quy lao động | "10 ngày **làm việc**" | **10 ngày** (không phải ngày làm việc) **và** chỉ áp dụng khi Công ty **từ 10 người lao động trở lên** | Điều 119 khoản 1, 2 |

- Mọi trích dẫn còn lại đã resolve và đối chiếu title thật: Điều 21, 24, 25, 29,
  34, 35, 45, 48, 104, 113, 119, 122, 131, 187, 188, 189 (BLLD) và Điều 38, 84
  (NĐ 145) — **tất cả HIGH, 0 LOW, 0 BOUNDARY, 0 target_doc invalid**.

## 5. Kết quả

| | Trước | Sau |
| --- | --- | --- |
| NQCT Điều | 45 | **82** (82/82 có chunk, `thiếu Điều: không`) |
| NQCT chunk | 45 (toàn ARTICLE) | **85** (81 ARTICLE + 4 CLAUSE) |
| NQCT cross-ref | 3 | **33** |
| Tổng chunk corpus | 1334 | **1374** (381+377+531+85) |
| Tổng ref corpus | 567 | **598** |
| Chunk vượt 1000 token | 0 | 0 |
| Chunk rỗng / trùng id | 0 / 0 | 0 / 0 |

Lưu ý: `NQCT` trước đây chỉ sinh chunk **ARTICLE** vì mọi Điều đều nhỏ hơn
ngưỡng 1000 token. Sau khi thêm Điều 46–82, Điều 49 (quy trình 4 bước) dài hơn
nên tách được 4 chunk **CLAUSE** — lần đầu corpus nội bộ có chunk cấp khoản, nhờ
đó câu hỏi "trình trong bao lâu" có thể trả lời ở đúng cấp khoản.

## 6. Refactor — bỏ số đếm gõ tay (nguyên nhân thật của việc này hỏng)

Trước khi làm bất cứ việc gì, `verify_db.py` đã **FAIL 6 check**. Nguyên nhân:
NQCT đã lên 45 Điều trong working tree từ trước, nhưng số kỳ vọng vẫn là literal
`NQCT: 18` / `TOTAL: 1307` rải rác ở 3 file. **Regenerate chunk không bao giờ sửa
hằng số Python** — đây là dạng invariant tệ nhất: hỏng *sau* mỗi thay đổi dữ liệu
hợp lệ, và thông báo lỗi chỉ vào file sai.

Sửa: thêm `scripts/corpus_expectations.py` làm nguồn duy nhất, tự dẫn
chunk/article/ref/total **từ `data/chunk/chunks_*.json`**;
`verify_db.py`, `embed_legal.py`, `verify_embeddings.py`, `seed_legal.py` import
từ đó. Giữ nguyên nguyên tắc "không lấy kỳ vọng từ DB" (lấy từ DB thì mọi phép
so sánh thành đúng vô nghĩa). Điều duy nhất **giữ** gõ tay là
`EXPECTED_BOUNDARY = 3` — đó là *ngân sách* cho chính sách suy luận
cross-ref, không phải hệ quả của dữ liệu.

Tripwire thật sự **không yếu đi**: `verify_db.py` V7 vẫn so sha256 từng file nguồn
với pin trong `source_manifest.json`, nên sửa nhầm chunk file vẫn bị bắt. Cần đổi
nguồn có chủ đích thì vẫn phải `--write-manifest` như runbook quy định.

Thêm: `validate_step3.py` trước đây hardcode `CODES = ["BLLD","ND283_2026","ND145_2020"]`
— **NQCT được seed vào DB nhưng không bao giờ được validate**. Giờ tự liệt kê mọi
`chunks_*.json`, và số Điều kỳ vọng lấy từ `document_tree_*.json` (cây parser tạo
ra từ markdown, độc lập với bước chunk) để check vẫn có ý nghĩa thay vì
tautology.

## 7. Eval — thêm 5 query, và 2 query cố tình KHÔNG ghim

`eval/legal_golden.json`: +Q11–Q15 (khiếu nại lần 1; khiếu nại lần 2; phản ánh
khách hàng mức C; bàn giao khi nghỉ việc; thẩm quyền mua sắm theo ngưỡng giá
trị). Đều pin **sau** khi chạy retrieval và đọc tay top-5.

Hai chủ đề đã thử nhưng **cố tình không đưa vào golden**, vì golden phải là một
bất biến đúng chứ không phải một ước muốn:

- **Điều 67** (thanh toán tiền lương khi chấm dứt HĐLĐ)
- **Điều 80** (đối thoại định kỳ)

### 8.1. NQCT vs luật — va chạm retrieval (phát hiện, chưa sửa)

Cả hai đều là nội dung mà **luật đã nói cùng ý**: BLLD Điều 48 quy định 14 ngày
làm việc để trả lương; NĐ 145 Điều 39 đã quy định đối thoại tại nơi làm việc.
Thử **8 cách đặt câu hỏi khác nhau** (thêm/bớt "nội quy lao động của công ty",
đổi từ khóa), kết quả:

| arm | Điều 67 | Điều 80 |
| --- | --- | --- |
| vector-only | miss (8/8) | miss (5/5) |
| bm25 | HIT | HIT |
| hybrid | HIT (7/8) | HIT |

**Nguyên nhân gốc:** `header_context` của chunk NQCT là
`[VĂN BẢN: NQLD-HRCORP-2026] > ...` — mã định danh **không chứa từ nào** nói đây
là *nội quy của công ty*. Vector không có tín hiệu nào để phân biệt "quy định của
công ty" với "quy định của luật", nên khi hai nguồn nói cùng ý thì nó nghiêng về
luật. BM25 không bị vì... cũng không có tín hiệu đó, nhưng `ts_rank` ưu tiên
khớp từ và chunk NQCT chứa đúng cụm "14 ngày làm việc" / "đối thoại định kỳ".

**Hướng sửa (chưa làm, vì ngoài phạm vi lần này và phải embed lại toàn bộ):**
đưa `document_type` vào `header_context` — ví dụ
`[VĂN BẢN NỘI BỘ: NỘI QUY LAO ĐỘNG (NQLD-HRCORP-2026)]`. Tốn 1 lần embed
1374 chunk (~1 phút), kỳ vọng là thu hẹp được va chạm này. Cần chạy lại
`eval_retrieval.py` và xem lại pin Q01–Q15 sau khi đổi.

### 8.2. Không hồi quy

Số liệu retrieval (15 query, `verify_embeddings.py`):

| arm | Hit@1 | Hit@5 | MRR | Article@5 |
| --- | --- | --- | --- | --- |
| vector | 0.600 → **0.733** | 0.700 → **0.800** | 0.625 → **0.750** | 0.700 → **0.800** |
| bm25 | 0.300 → **0.533** | 0.700 → **0.800** | 0.470 → **0.647** | 1.000 → **1.000** |
| hybrid | 0.500 → **0.667** | 0.900 → **0.933** | 0.650 → **0.767** | 1.000 → **1.000** |

(Nhớ: số cột phải là của **cùng 10 query cũ**, đọc lại từ
`eval/results/retrieval_eval_20261001_114024.md`, vì mẫu đã đổi.)

`V4.vector_top5_contains_expected` và `V5.article_in_top5.vector` vẫn **FAIL** —
nhưng chỉ với `['Q03','Q09','Q10']`, và **đây là lỗi có sẵn từ trước**: report
`retrieval_eval_20261001_114024.md` đã ghi Q03/Q09/Q10 vector rank = `None` khi
corpus còn 10 query. Hybrid và bm25 trả về cả 3 câu đó. Ghi ra đây thay vì giấu
vì `verify_embeddings.py` xanh hoàn toàn sẽ là hiểu sai.

## 9. Kiểm chứng

```
python -m data_pipeline_steps.step3.run_step3 --doc noi_quy_mau_cong_ty
python -m data_pipeline_steps.step3.validate_step3   # NQCT: 82/82 Điều, 0 thiếu
python scripts/corpus_expectations.py                # in số đúng
python scripts/seed_legal.py                         # exit 0
python scripts/embed_legal.py                        # 79 chunk mới, 3 request
python scripts/seed_hr_from_legal.py                 # document_chunks 1374
python scripts/verify_db.py --write-manifest         # re-pin sha256 (có chủ đích)
python scripts/verify_db.py                          # 77 PASS, 0 FAIL
python scripts/verify_embeddings.py                  # 76 PASS, 2 FAIL (Q03/Q09/Q10 có sẵn)
python -m pytest -q                                  # 169 passed
```

## 10. Việc còn lại

1. ~~Refresh `handoff/*.dump` + sha256~~ — **xong 2026-10-03**: dump `full` đã
   re-dump ở head `0009` (`-Z 9`), `pg_restore` thử vào DB tạm `p029_restore_verify`
   để đối chiếu (4 / 1374 / 598 / 1374 / 1374, `emb_null = 0`, alembic `0009`)
   trước khi thay thế; sha256 đã cập nhật và khớp.
2. **Quyết định về mục 8.1** — có bổ sung `document_type` vào `header_context`
   để giảm va chạm NQCT-vs-luật không. Đây là cải thiện chất lượng retrieval,
   không chỉ là sửa test.
3. **Đánh giá lại V4/V5** theo mục 9 của `CHANGELOG_B6B7.md` — giờ đã rõ hơn:
   3 miss là do đánh đổi đã biết giữa vector-only và hybrid, đã được ghi nhận
   chứ không phải hồi quy của lần đổi dữ liệu này.
4. **Nếu muốn thêm văn bản thứ 5** (quy chế quản trị công ty): `validate_step3`
   và `corpus_expectations.py` đã tự liệt kê, nên chỉ còn thêm `DOC_ID_MAP` +
   `DOCUMENTS` + `LEGAL_DOCS` như runbook mục 4 nói.