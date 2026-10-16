# Hai nhánh hội thoại và semantic recheck đã triển khai

Phiên bản: `intent-router-v5-rule-recheck-social-help`. Ngày: 16/10/2026.

## Hành vi runtime

- Graph giữ `intent → route_after_intent → node`. Bổ sung `general_chat` và `system_help`, kết thúc tại `END` như các nhánh trả lời khác.
- `route_rules.py` giữ bộ đối chiếu regex/keyword có chuẩn hóa dấu, hoa/thường và khoảng trắng. Match chỉ trả giả thuyết kèm rule ID, route ứng viên và cụm đã match (dạng chuẩn hóa).
- Không OR các tín hiệu lexical vào `IntentDecision`. Có bất kỳ match nào thì kiểm tra semantic lại đúng một lần, kể cả ứng viên trùng nhánh ban đầu; nhiều match dùng chung lần kiểm tra.
- Recheck đọc câu gốc, ngữ cảnh, quyết định ban đầu, các giả thuyết và toàn bộ route cards. Nó có thể giữ nhánh ban đầu, chọn ứng viên hoặc chọn nhánh hợp lệ khác. Output là `confirmed` hoặc `needs_clarification`.
- Khi cần làm rõ, `disambiguate` hỏi câu cụ thể. Metadata lưu câu gốc, câu hỏi làm rõ và reference tới lượt gốc; câu trả lời tiếp theo được đọc cùng chúng. Planner và các node đọc/tra cứu nghiệp vụ nhận đúng ngữ cảnh làm rõ, không nhận lịch sử chuyện phiếm.
- Output mâu thuẫn có một lần recheck; lỗi schema/provider sau ngân sách phục hồi giữ state và báo lỗi để thử lại. Không tự chạy fact planner vì router lỗi. Không chọn cạnh theo score của regex hoặc coi confidence tự khai là xác suất đúng.

## Nội dung hai nhánh

`system_help` trả lời từ catalog 12 topic: giới thiệu, khả năng, quyền hạn, bắt đầu, workflow, biên bản, vai trò, trả lại hồ sơ, nguồn, độ tin cậy, riêng tư và trò chuyện. Topic IDs nằm trong schema router; matcher trong node hỗ trợ cách diễn đạt khác. Không có LLM viết lại đáp án. Khả năng tra web chỉ được mô tả là đang bật khi flag và provider/credential tương ứng đã cấu hình.

`general_chat` dùng provider đang cấu hình, không bind tools, không truyền case profile/facts/report vào prompt. Có prompt tiếng Việt thân thiện, dí dỏm có chừng mực và giới hạn thẩm quyền. Luồng gồm moderation input → sinh câu trả lời → moderation output trước khi phát. Nội dung rủi ro/lỗi kiểm tra dùng mẫu an toàn; không phát draft chưa được kiểm tra. Moderation dùng prompt phân loại riêng trên cùng provider, chưa phải một classifier được huấn luyện độc lập. Không tự đổi provider.

## Dữ liệu và UI

- Hai nhánh mới là `state_update=preserve`, `task_change=keep`; không ghi facts, thu hồi báo cáo, chuyển trạng thái, gửi phiếu hoặc phát notification nghiệp vụ.
- Lưu scope trên cả USER và ASSISTANT. Context nghiệp vụ lọc social/help/clarification trước khi lấy cửa sổ gần nhất, kể cả transcript fallback. Chỉ casual messages đã được phép phát mới vào cửa sổ general riêng.
- Dùng snapshot facts để giữ đúng `facts_locked`; `CaseState` khai báo rõ `accepted_keys` và `validation` để LangGraph không bỏ chúng.
- `TurnResponse` bổ sung optional `reply_kind` và `state_update`; frontend giữ cache nghiệp vụ khi phản hồi preserve. Cơ chế hiện chữ dần hiện có tiếp tục dùng sau khi kiểm tra xong output.
- Metadata dùng JSONB messages hiện có, không cần migration. Quyền truy cập, trạng thái cho phép chat và authorization tại API vẫn được giữ.

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `SYSTEM_HELP_ENABLED` | `true` | Bật catalog Q&A; tắt thì node trả thông báo tạm tắt |
| `GENERAL_CHAT_ENABLED` | `true` | Bật trò chuyện đời thường |
| `GENERAL_CHAT_TIMEOUT_SECONDS` | `20` | Timeout mỗi bước moderation/generation |
| `GENERAL_CHAT_RATE_LIMIT` | `12` | Số lượt general/actor/phút, giới hạn theo process |
| `INTENT_TOTAL_TIMEOUT_SECONDS` | `60` | Ngân sách thời gian toàn bộ phân loại và recheck |

Rate limit bộ nhớ hiện áp dụng theo worker; nếu chạy nhiều worker/replica và cần quota chung, phải chuyển bộ đếm sang kho dùng chung. Các API model vẫn dùng credentials/provider đã cấu hình. Flag tắt không xóa hội thoại hoặc thay dữ liệu.

## Kiểm chứng

- Bộ regression liên quan gồm routing, memory, minutes, chat, enterprise workflow, manager review và returned minutes: 180 passed, 3 integration test không chạy trong lệnh mặc định.
- `P029_RUN_DB_TESTS=1 .venv/bin/pytest tests/test_social_workflow_database.py -q`: API thật + PostgreSQL đã qua. Kiểm tra help → hỏi rõ → trả lời làm rõ → general; dữ liệu giả được rollback, facts/report/status/pending task giữ nguyên.
- Frontend build, Ruff và `git diff --check` qua.
- Live routing smoke với `deepseek-flash`: 10/10 câu tổng hợp qua, có cả ba phản ví dụ keyword override, mixed greeting/fact và workflow. Mọi mẫu có rule hit đều ghi nhận `recheck=confirmed`. Một câu gợi ý ăn uống qua đủ input moderation, generation và output moderation.
- Live moderation smoke: 6/6 mẫu qua, gồm gây hại, injection, tự hại, mệt mỏi thông thường, output giả nhận đã phê duyệt và một lời từ chối an toàn.
- Kết quả lưu tại `eval/routing/results.json` và `eval/routing/safety-results.json`. Đây là smoke set nhỏ; không phải ước lượng accuracy production hoặc bảo đảm 100% an toàn/đúng ý định. Model recheck và moderation vẫn có thể cùng sai.

Chạy lại offline:

```sh
.venv/bin/pytest tests/test_social_routing.py tests/test_general_chat.py tests/test_conversation_contract.py tests/test_clarify_planner.py -q
```

Các lệnh dưới gọi model thật và có thể phát sinh phí; chỉ dùng dữ liệu giả trong fixture:

```sh
PYTHONPATH=. .venv/bin/python eval/routing/run.py --live --chat
PYTHONPATH=. .venv/bin/python eval/routing/check_safety.py --live
```

Theo dõi `orchestrator_route_trace`: initial route, selected route, rule IDs và recheck status. Metadata giữ trace để đối chiếu; log kỹ thuật không in toàn bộ prompt hoặc cụm thông tin người dùng match được. Backend local đã được build/restart để áp dụng phiên bản này; endpoint health kiểm tra thành công.
