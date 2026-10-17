# Evaluation Report

> Báo cáo đánh giá chất lượng sản phẩm theo tiêu chí BTC, cập nhật ngày 2026-10-17.
> Tổng hợp từ các artifact đã lưu trong `eval/`; không chạy lại đánh giá dùng mô hình/API trong lần cập nhật này. Các nhãn và đáp án tham chiếu vẫn là bản nháp chờ chuyên gia rà soát.

## 1. Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Response accuracy | >80% | Chưa đo accuracy đầu cuối. RAGAS factual correctness của đánh giá hồ sơ: 0.5320 (5 ca); kiểm tra xác định với chứng cứ cố định: 5/10 ca đạt | Chưa đủ cơ sở xác nhận đạt; các kết quả hiện có cho thấy cần cải thiện |
| Response latency | <3s | Chưa đo đầu cuối. Routing/trích xuất: p50 5.148s, p95 8.137s; retrieval có điều tiết API: trung bình 33.542s | Chưa xác nhận đạt; p50 thành phần routing/trích xuất đã vượt 3s |
| User satisfaction | >4/5 | Chưa có dữ liệu khảo sát người dùng | Chưa đánh giá |
| Test coverage | >60% | Chưa có báo cáo đo code coverage | Chưa đánh giá |

Điểm RAGAS, tỷ lệ ca đạt kiểm tra và accuracy trả lời là các đại lượng khác nhau; không quy đổi chúng thành một tỷ lệ chính xác chung. Thời gian retrieval bao gồm khoảng cách tối thiểu 7 giây giữa các request rerank, nên không dùng làm độ trễ phục vụ người dùng.

### Kết quả thành phần

| Hạng mục | Phạm vi và kết quả | Nguồn |
| --- | --- | --- |
| Kho tri thức / ingestion | 14/16 ca đạt; bảo toàn 187/189 đoạn nguồn (98.94%); nội dung hiển thị cho retrieval đạt 98.41%; metadata đúng trên 187 đoạn được bảo toàn; tìm được 3/5 dẫn chiếu mong đợi | [Báo cáo ingestion](../ingestion/results/saved_corpus/report.md) |
| Retrieval | 20/20 ca chạy thành công và đạt kiểm tra đã gán nhãn; final recall 1.0000 trên 19 ca có điểm; 1 ca kiểm tra kết quả rỗng đạt; judgment coverage 25.88% | [Báo cáo retrieval có điều tiết](../retrieval/results/golden_paced/report.md) |
| Routing và trích xuất | Hoàn thành 46/48 ca, đạt toàn bộ yêu cầu 45/48; routing đúng 28/28 ca chấm được, 2 ca lỗi xử lý; trích xuất đạt 17/18 ca, F1 sau kiểm tra Python 0.9825 | [Báo cáo routing](../routing/results/golden_live/report.md) |
| Đánh giá hồ sơ với retrieval trực tiếp | 5/5 ca có đủ 4 điểm RAGAS; faithfulness 0.8891, factual correctness 0.5320, context precision 0.9239, context recall 0.8156 | [Báo cáo case assessment](../case_assessment/results/run_20261017T030843Z/report.md) |
| Chất lượng đánh giá và trả lời với chứng cứ cố định | 10/10 ca được chấm, 5/10 đạt kiểm tra xác định: ca có nguồn 0/5, ca không có chứng cứ 5/5 | [Báo cáo answer quality](../answer_quality/results/run_20261017T030843Z/report.md) |

Lần chạy assessment/answer quality ngày 2026-10-17 dùng DeepSeek (`deepseek-flash`) để sinh đầu ra và Mistral (`ministral-8b-2512`) làm giám khảo RAGAS. Toàn bộ 40 điểm ngữ nghĩa của answer quality và 20 điểm của case assessment đã có; một HTTP 503 được khôi phục qua retry. Chi tiết tại [tổng hợp lần chạy](assessment_answer_quality_20261017.md).

| Answer quality — trung bình 10 ca | Report | Answer |
| --- | ---: | ---: |
| Faithfulness | 0.784 | 0.720 |
| Factual correctness | 0.746 | 0.785 |

Trên riêng 5 ca có nguồn, factual correctness của report là 0.618 và answer là 0.570. Kết quả tổng hợp chịu ảnh hưởng của 5 ca không có chứng cứ, nên cần đọc riêng hai nhóm.

## 2. Test Results

### Unit Tests

Bản [tổng hợp lần chạy 2026-10-17](assessment_answer_quality_20261017.md) ghi nhận **3 regression tests passed** sau khi chuẩn hóa heading null trong fixture thành chuỗi rỗng. Đây là kết quả đã lưu, không đại diện cho toàn bộ bộ test.

Thử chạy toàn bộ bộ test trong môi trường hiện tại ngày 2026-10-17:

```text
$ python3 -m pytest tests/ -q --tb=short
/usr/bin/python3: No module named pytest
Exit code: 1
```

Bộ test chưa khởi chạy do thiếu `pytest`; không kết luận test pass/fail từ lỗi môi trường này. Chưa có số liệu coverage. Sau khi chuẩn bị môi trường và cài dependency từ `requirements.txt`, có thể chạy lại bằng `python3 -m pytest tests/ -v --tb=short`; cần công cụ đo coverage riêng để kiểm chứng mục tiêu >60%.

### Integration Tests / Component Evaluations

- **Ingestion:** đối chiếu nguồn với tệp chunk đã lưu, chưa replay toàn bộ pipeline hoặc kiểm tra DB/vector đang chạy. Hai ca ND145_2020-A069 và A070 thiếu/thay đổi đoạn nguồn và thiếu dẫn chiếu; một đoạn chỉ còn trong metadata. Danh mục NQCT còn nhãn điều ngoài nguồn.
- **Retrieval:** chạy graph production với giao dịch chỉ đọc; không có lỗi xử lý hay đầu ra suy giảm. Có 17/20 ca vượt ngân sách chứng cứ và 1 ca thiếu cả căn cứ nội bộ lẫn pháp luật. Snapshot có 0 cạnh dẫn chiếu nên chưa đo được lợi ích mở rộng đồ thị. Nhãn chỉ bao phủ 25.88% đầu ra; recall cao chưa chứng minh precision hoặc đầy đủ căn cứ.
- **Routing/trích xuất:** R16 và R20 dùng fallback sau kiểm tra lại thất bại, được tính là lỗi xử lý với điểm null. F01 mất `notice_form` sau kiểm tra Python dù đầu ra mô hình có tình tiết này.
- **Case assessment:** chạy retrieval DB thật rồi đưa passages vào graph đánh giá; đủ điểm cho 5 ca. Không bao gồm hội thoại đầu cuối, lưu hồ sơ hay phê duyệt.
- **Answer quality:** dùng chứng cứ cố định. CA01 thiếu bao phủ tình tiết cần bổ sung; CA02–CA04 đề xuất `WARNING` khác tham chiếu nháp; CA05 khác cả trạng thái và chế tài. Tất cả ca có nguồn vẫn đạt kiểm tra giữ tình tiết đã xác nhận, không bịa tình tiết được đánh dấu chưa biết, toàn vẹn trích dẫn và các ràng buộc human-review/ticket.

Kiểm tra missing facts so khớp key chính xác, cần đọc capture trước khi kết luận thiếu về ngữ nghĩa. Trích dẫn nguyên văn không tự xác nhận suy luận pháp lý đúng. Bộ dữ liệu nhỏ, nhãn nháp và các phép đo thành phần chưa đủ để chứng minh chất lượng vận hành đầu cuối.

## 3. User Feedback

Chưa có bản ghi phản hồi người dùng hoặc khảo sát rating trong các artifact đánh giá được tổng hợp. Không có cơ sở tính điểm hài lòng trung bình hay xác nhận mục tiêu >4/5.

| Nhóm cần thu thập | Nội dung đánh giá | Rating |
| --- | --- | --- |
| HR / người lập hồ sơ | Độ rõ của câu trả lời, tình tiết cần bổ sung, khả năng sử dụng trong quy trình | Chưa thu thập |
| Pháp chế / người rà soát | Chất lượng căn cứ, đề xuất xử lý và mức đầy đủ của báo cáo | Chưa thu thập |

## 4. Demo Results

- Ngày demo: chưa có biên bản xác nhận; 2026-10-17 là ngày chạy đánh giá kỹ thuật được tổng hợp, không phải ngày demo đã xác minh.
- Người tham gia: chưa có dữ liệu.
- Feedback chung: chưa có phản hồi từ phiên demo.
- Issues kỹ thuật cần kiểm tra khi demo: đề xuất chế tài khác tham chiếu, thiếu tình tiết cần bổ sung, fallback routing, mất `notice_form`, thiếu nội dung/dẫn chiếu trong chunk và độ trễ thành phần vượt mục tiêu.
- Chưa có kết quả xác minh trọn luồng hội thoại → tạo/lưu hồ sơ → rà soát/phê duyệt trong các báo cáo này.

## 5. Action Items

- [ ] HR/pháp chế rà soát nhãn, căn cứ và đáp án tham chiếu trước khi dùng kết quả để nghiệm thu.
- [ ] Rà soát CA01–CA05, cải thiện bao phủ tình tiết cần bổ sung và việc chọn trạng thái/chế tài; đọc capture để phân biệt lỗi ngữ nghĩa với sai khác key.
- [ ] Sửa kiểm tra Python làm mất `notice_form` ở F01 và xử lý fallback R16/R20; chạy lại các ca liên quan.
- [ ] Khôi phục đoạn nguồn và dẫn chiếu thiếu ở ND145_2020 Điều 69–70, rà soát nhãn điều NQCT và kiểm chứng dữ liệu sau nạp DB/vector.
- [ ] Mở rộng nhãn liên quan cho retrieval, xử lý cảnh báo ngân sách chứng cứ và bổ sung dữ liệu cạnh để đo graph expansion.
- [ ] Đo latency đầu cuối p50/p95 với cấu hình phục vụ thực tế, tách thời gian chờ điều tiết benchmark và thời gian từng thành phần.
- [ ] Chuẩn bị môi trường test, chạy toàn bộ bộ test và đo code coverage để đối chiếu mục tiêu >60%.
- [ ] Tổ chức demo đầu cuối, lưu ngày/người tham gia/issues và thu thập rating 1–5 từ người dùng.
