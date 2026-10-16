# Hợp đồng regex/keyword → LLM recheck → làm rõ

> Đã triển khai phiên bản `intent-router-v5-rule-recheck-social-help`. Xem [hành vi thực tế và kết quả kiểm thử](orchestrator-social-implementation.md). Nội dung dưới lưu lại thiết kế/nghiên cứu trước triển khai.

Trạng thái: thiết kế chốt theo yêu cầu người dùng, chưa triển khai runtime. Đây là phần bổ sung cho solution hai nhánh `general_chat` và `system_help`.

## 1. Quyết định

Giữ bộ phát hiện regex/keyword. Bỏ quyền ghi đè route và quyền bổ sung hard signals vào kết quả semantic gốc. Bất kỳ rule hit nào cũng kích hoạt một lượt LLM kiểm tra lại, kể cả route gợi ý trùng route ban đầu. Nếu LLM chưa xác định được ý định thì hỏi người dùng, không tự chạy một nhánh nghiệp vụ.

Các rule hiện chủ yếu là phép kiểm tra substring; khi triển khai cần gọi đúng là lexical detector và có thể dùng regex có ranh giới phù hợp. Thay cơ chế override không đòi hỏi biến mọi substring thành regex ngay.

## 2. Vị trí trong graph

```text
intent node hiện tại
  1. Semantic LLM → initial IntentDecision
  2. Lexical detector → matches + route candidates (không sửa bước 1)
  3. Có match → LLM semantic recheck tối đa một lần
  4. Kiểm chứng output và quyết định cuối
        ↓
route_after_intent hiện tại
  confirmed → node chuyên trách, gồm hai node mới
  unresolved → disambiguate → hỏi người dùng → END
```

Không thêm router trước intent node, không tạo orchestrator thứ hai và không cho node general/help tự gọi workflow. Conditional edges từ các nhánh nghiệp vụ giữ nguyên.

## 3. Đầu ra lexical detector

Detector trả tất cả match liên quan, không chọn một ứng viên bằng thứ tự ưu tiên cũ:

```json
{
  "matches": [
    {
      "rule_id": "mentions_approval",
      "matched_text": "phê duyệt",
      "candidate_route": "unsupported",
      "hypothesis": "Có thể là yêu cầu thực hiện phê duyệt; cũng có thể chỉ đang hỏi về quyền hoặc trạng thái."
    }
  ]
}
```

Match là giả thuyết, không phải bằng chứng rằng ý định đó đã đúng. Không OR `asks_prohibited_action=true` vào quyết định LLM chỉ vì có match. Không biến số rule match thành confidence hoặc chọn nhánh theo điểm keyword.

Nếu không match nhưng output model sai schema/mâu thuẫn thì vẫn dùng cơ chế validation/recovery. Không có match cũng không chứng minh model đúng nghĩa.

## 4. Input và instruction cho semantic recheck

Input gồm:

- Latest user message nguyên vẹn và reference tới message gốc.
- Ngữ cảnh gần nhất cần thiết, tác vụ đang chờ và câu hỏi đang được trả lời.
- Initial IntentDecision chưa bị lexical detector chỉnh sửa.
- Các match, cụm từ gốc và giả thuyết candidate route.
- Route cards của các ứng viên và danh sách các route hợp lệ còn lại.

Instruction trọng tâm:

```text
Kiểm tra lại ý định của latest user message trong ngữ cảnh được cung cấp.
Quyết định ban đầu và lexical candidates đều là giả thuyết, không phải đáp án.
Không ưu tiên ứng viên chỉ vì được rule phát hiện hoặc vì là lựa chọn ban đầu.

So sánh mục đích và hành vi ngôn ngữ: hỏi khả năng/quyền, hỏi thông tin đang lưu,
yêu cầu thực hiện thao tác, cung cấp tình tiết, hỏi quy định hay trò chuyện.
Xét phủ định, câu trích dẫn, đối tượng, thời điểm và các mệnh đề còn lại.
Pending task không biến câu hỏi bên lề thành lệnh tiếp tục nghiệp vụ.

Chọn nhánh ban đầu nếu nó phù hợp; chọn candidate của rule nếu ý nghĩa thực sự
ủng hộ; được chọn route hợp lệ khác nếu cả hai đều sai. Không ép chọn giữa hai
ứng viên thiếu căn cứ. Không dùng confidence tự khai làm bằng chứng duy nhất.

Nếu chưa đủ thông tin, trả clarification với một câu hỏi cụ thể để phân biệt
các mục tiêu còn khả dĩ. Không thực hiện thao tác hoặc đổi state hồ sơ.
Chỉ trả output schema đã định nghĩa; không cần suy luận nội bộ dài.
```

Recheck được phép chọn một nhánh thứ ba vì initial decision và rule đều có thể sai. Đây vẫn là cùng nhiệm vụ phân loại, không mở thêm tool hoặc quyền thực thi.

## 5. Output recheck và hành vi Python

Hai trạng thái phân biệt bằng schema:

```text
CONFIRMED:
  final_decision = một IntentDecision hợp lệ, nhất quán
  evidence = đoạn dẫn ngắn với source rõ ràng
  resolution = keep_initial | select_rule_candidate | select_other
  reason_code = mã ngắn phục vụ trace

NEEDS_CLARIFICATION:
  final_decision = không có quyết định nghiệp vụ để thực hiện
  clarification_question = câu hỏi ngắn phân biệt các mục tiêu
  candidate_routes = các nhánh còn khả dĩ
```

Python không chuyển `NEEDS_CLARIFICATION` thành một route bằng cách nhìn score. Nó dùng `Route.CLARIFY`/node `disambiguate` hiện có và hiển thị câu hỏi. Với `CONFIRMED`, Python kiểm tra allowlist, route/action contract và các giới hạn; việc gọi node vẫn qua `route_after_intent`.

Không lấy `confidence > 0.6` làm định nghĩa của CONFIRMED. Confirmation là một quyết định có cấu trúc dựa trên câu gốc; chất lượng quyết định này phải được đánh giá, không có bảo đảm đúng tuyệt đối.

Sai schema hoặc lỗi provider là lỗi xử lý, không tự động là bằng chứng người dùng nói mơ hồ. Hết ngân sách phục hồi thì báo chưa xử lý được để thử lại, giữ state; không rơi về fact planner chỉ vì lỗi kỹ thuật.

## 6. Ví dụ bắt buộc

| Latest message | Initial / rule candidate | Recheck cần đạt |
| --- | --- | --- |
| AI có quyền phê duyệt không? | system_help / unsupported vì “phê duyệt” | Xác nhận system_help, không hỏi lại nếu nghĩa rõ |
| Hồ sơ này đang chờ phê duyệt ở đâu? | case_qa / unsupported | Xác nhận case_qa |
| Hồ sơ này hiện nay đang ở bước nào? | case_qa / external_research | Xác nhận case_qa |
| Phê duyệt hồ sơ này ngay giúp tôi | system_help (giả lập chọn sai) / unsupported | Chọn unsupported, không phê duyệt |
| Bạn xử lý phần duyệt giúp tôi | system_help / unsupported | Nếu context không đủ, hỏi người dùng đang muốn hướng dẫn hay yêu cầu thực hiện |
| Theo quy định hiện nay, lập biên bản vụ này giúp tôi | workflow_action / external_research và policy_qa | Xác định mục tiêu lập biên bản, không tự bỏ tác vụ chính do keyword |
| Cả initial lẫn rule đều sai | Hai route không phù hợp | Cho phép chọn route thứ ba có căn cứ hoặc hỏi rõ |

Ví dụ clarification: “Bạn muốn mình giải thích quyền phê duyệt của AI, hay đang yêu cầu thực hiện phê duyệt hồ sơ?” Không hỏi chung chung “ý bạn là gì?” nếu đã xác định được các mục tiêu cần phân biệt.

## 7. Tiếp nhận câu trả lời làm rõ

Lưu câu hỏi, message gốc và các mục tiêu đang phân biệt dưới metadata/ngữ cảnh clarification riêng. Khi người dùng trả lời “tôi chỉ hỏi quyền của AI”, intent node nhận cả câu gốc và câu trả lời mới để chốt `system_help`.

Không thay `pending_action`, active fact schema hay open questions nghiệp vụ bằng câu hỏi clarification. Khi đang đợi clarification, không coi câu trả lời ngắn của người dùng là xác nhận facts của tác vụ HR cũ. Người dùng đổi chủ đề rõ ràng vẫn được nhận diện theo latest message, không bị khóa trong câu hỏi cũ.

## 8. Giới hạn và nghiệm thu

- Tối đa một semantic recheck mỗi lượt; retry kỹ thuật có ngân sách riêng và giới hạn tổng thời gian. Không recheck lặp chỉ vì kết quả mới vẫn chứa từ đã match.
- Cùng route ở initial/rule vẫn qua recheck theo yêu cầu; không tự suy ra hai bên đồng ý thì chắc đúng.
- Nếu nhiều match, gộp vào một lần recheck, không gọi model một lần cho từng rule.
- Lượt cần làm rõ/lỗi không ghi facts, không đổi case status, không thu hồi báo cáo hay gửi phiếu.
- Trace gồm initial route, rule hits, recheck outcome, final route và reason code; không log nguyên dữ liệu nhạy cảm không cần thiết.
- Đo lợi ích semantic, số lần hỏi lại không cần thiết, latency, chi phí và lỗi cuối cùng so với baseline. Các lượt phổ biến có từ như “luật” có thể phát sinh thêm lần gọi model; đây là đánh đổi cần công bố và đo.
- Thiết kế không bảo đảm 100%: model recheck có thể đồng ý với một cách hiểu sai, và lexical detector có thể bỏ sót lỗi. Không dùng đồng thuận hoặc output hợp lệ thay cho eval.

Các test bắt buộc: hit không sửa raw decision; hit trùng route vẫn recheck; nhiều hit chỉ một lần; recheck chọn initial/rule/other; ambiguous đi disambiguate; clarification theo đúng câu gốc; provider/schema failure không mutate; regression ba phản ví dụ đã ghi nhận và các invariant của hai nhánh mới.
