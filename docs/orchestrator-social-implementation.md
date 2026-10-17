# Hai nhánh hội thoại và semantic recheck đã triển khai

Phiên bản: `intent-router-v8-concise-help-cards`. Cập nhật: 17/10/2026.

## Hành vi runtime

- Graph giữ `intent → route_after_intent → node`. Bổ sung `general_chat` và `system_help`, kết thúc tại `END` như các nhánh trả lời khác.
- `route_rules.py` giữ bộ đối chiếu regex/keyword có chuẩn hóa dấu, hoa/thường và khoảng trắng. Match chỉ trả giả thuyết kèm rule ID, route ứng viên và cụm đã match (dạng chuẩn hóa).
- Không OR các tín hiệu lexical vào `IntentDecision`. Có bất kỳ match nào thì kiểm tra semantic lại đúng một lần, kể cả ứng viên trùng nhánh ban đầu; nhiều match dùng chung lần kiểm tra.
- Recheck đọc câu gốc, ngữ cảnh, quyết định ban đầu, các giả thuyết và toàn bộ route cards. Nó có thể giữ nhánh ban đầu, chọn ứng viên hoặc chọn nhánh hợp lệ khác. Output là `confirmed` hoặc `needs_clarification`.
- Khi cần làm rõ, `disambiguate` hỏi câu cụ thể. Metadata lưu câu gốc, câu hỏi làm rõ và reference tới lượt gốc; câu trả lời tiếp theo được đọc cùng chúng. Planner và các node đọc/tra cứu nghiệp vụ nhận đúng ngữ cảnh làm rõ, không nhận lịch sử chuyện phiếm.
- Output mâu thuẫn có một lần recheck; lỗi schema/provider sau ngân sách phục hồi giữ state và báo lỗi để thử lại. Không tự chạy fact planner vì router lỗi. Không chọn cạnh theo score của regex hoặc coi confidence tự khai là xác suất đúng.

## Nội dung hai nhánh

`system_help` lấy đáp án từ catalog Q&A đã duyệt sau khi router chọn topic theo ý nghĩa câu hỏi. Ngay trong node này, `format_help_reply` dùng provider hiện cấu hình để diễn đạt đáp án phù hợp với câu hỏi và memory. Prompt gồm system prompt riêng, câu hỏi hiện tại, đáp án Q&A và `context_memories` (turn context đã có, các lượt Q&A gần nhất, ngữ cảnh làm rõ), cùng scope hồ sơ/chat độc lập. Không truyền toàn bộ state hoặc credentials vào model, không thêm node/edge hay thay bộ chọn nhánh.

Model chỉ diễn đạt nội dung đã duyệt, dùng memory để hiểu câu hỏi nối tiếp, không thêm chức năng/quy trình, tự lấy memory làm nguồn kiến thức hay thực hiện tác vụ. Đây là ràng buộc bằng prompt, không phải bộ kiểm chứng tính đúng đắn độc lập. Không bind tools. Đầu ra JSON có trường `answer` được validation. Khi lỗi, timeout, thiếu credential hoặc đầu ra không hợp lệ, dùng nguyên đáp án Q&A trước bước diễn đạt. Không gọi formatter khi Q&A tắt hoặc không tìm được đáp án. Khả năng tra web trong đáp án nguồn vẫn được xác định từ flag và provider/credential hiện có.

Kiểm tra refactor diễn đạt Q&A: **210 regression tests passed**, **2 integration tests PostgreSQL passed** (dữ liệu giả rollback). Kiểm tra đầu vào prompt/memory, đầu ra lỗi/rỗng/quá dài, timeout, thiếu credential, bỏ qua formatter khi không có đáp án/tắt Q&A, giữ facts/pending task và memory qua hai API. Smoke trực tiếp formatter với model thật gồm ba câu: câu hỏi nối tiếp không lặp bước tạo hồ sơ đã hoàn thành; câu hỏi cần chuẩn bị gì giữ đúng đáp án thông tin; câu yêu cầu giả nhận đã phê duyệt được từ chối trong phản hồi. Cả ba dùng output model, không dùng đáp án fallback. Đây là smoke nhỏ, không phải đánh giá toàn bộ router hay bảo đảm model luôn giữ đúng nội dung.

### Q&A hướng dẫn lập biên bản

Card `system_help` mô tả ngắn phạm vi hướng dẫn sử dụng và phân biệt với thực hiện tác vụ, cung cấp fact, đọc hồ sơ hoặc hỏi căn cứ pháp lý. Router nhận mô tả ngắn của từng topic, thay vì toàn bộ đáp án hay danh sách cách hỏi mẫu:

- `minutes_getting_started`: cách bắt đầu, vị trí thao tác, các bước tạo biên bản.
- `minutes_required_information`: thông tin cần chuẩn bị/cung cấp; gồm hồ sơ/nhân viên, vụ việc và tài liệu liên quan nếu có. Nội dung cần bổ sung phụ thuộc tình huống, không ấn định một bộ tình tiết bắt buộc cho mọi vụ việc.
- `minutes_help`: xem, sửa, xác nhận và xuất bản nháp hiện có.

Câu “tôi muốn lập biên bản thì phải cung cấp những thông tin gì” cần topic thông tin chuẩn bị, không phải hướng dẫn bấm nút. Việc chọn topic vẫn thuộc bộ phân loại ngữ nghĩa hiện có. Không có lookup theo nguyên câu, đường tắt bỏ qua model hay regex riêng ép câu hỏi lập biên bản vào Q&A. Các hàm `route_turn`, `_classify_turn`, `_recheck` giữ control flow như bản gốc; graph/nodes/edges không đổi trong lần tinh gọn này. Q&A không gọi Planner/Extract Fact, không tạo bản nháp hay đổi tác vụ đang chờ.

`no_matching_answer` và lựa chọn topic rỗng trả nguyên văn: “Tôi tạm thời chưa thể trả lời cho bạn, bạn có thể hỏi kỹ hơn hoặc hỏi câu khác.” Không thêm phần giới thiệu hay chuyển sang retrieval. Vẫn tuân theo `SYSTEM_HELP_ENABLED`.

Trường chẩn đoán `reason` được giới hạn 300 ký tự trước validation để độ dài giải thích không làm mất quyết định hợp lệ; các kiểm tra route/action/công cụ giữ nguyên.

Kiểm tra hồi quy mới: **183 passed** gồm minutes usage help, social routing, chat độc lập, conversation contract, minutes workflow, clarify/planner và pipeline. Kiểm tra cấu trúc xác nhận hai file graph không đổi trong lượt chỉnh sửa; AST của `route_turn`, `_classify_turn`, `_recheck` khớp bản gốc trong Git. Các bài dùng model mock kiểm tra state/công cụ và hợp đồng, không chứng minh độ chính xác model live.

Smoke model thật: câu hỏi cần thông tin trong ảnh và hai cách diễn đạt khác đều chọn `minutes_required_information`; câu hỏi thao tác chọn `minutes_getting_started`. Các câu yêu cầu lập ngay, cung cấp fact và hỏi căn cứ pháp lý vẫn chọn nhánh riêng. Trong lô tám câu có một lỗi recheck tạm thời ở câu không có Q&A; chạy riêng lại câu đó chọn `no_matching_answer`. Không thêm đường tắt hay thay xử lý lỗi để ép mẫu này qua. Kết quả này là smoke có giới hạn, không phải cam kết mọi câu hỏi luôn được phân loại đúng. Backend Docker đã được build/nạp lại để dùng bản v8; PostgreSQL giữ nguyên.

`general_chat` dùng provider đang cấu hình, không bind tools, không truyền case profile/facts/report vào prompt. Có prompt tiếng Việt thân thiện, dí dỏm có chừng mực và giới hạn thẩm quyền. Luồng gồm moderation input → sinh câu trả lời → moderation output trước khi phát. Nội dung rủi ro/lỗi kiểm tra dùng mẫu an toàn; không phát draft chưa được kiểm tra. Moderation dùng prompt phân loại riêng trên cùng provider, chưa phải một classifier được huấn luyện độc lập. Không tự đổi provider.

## Semantic dialogue memory

`dialogue_context.py` bổ sung bước LLM phân tích mối liên hệ USER/ASSISTANT **trước** graph ở cả `_plan` của hồ sơ và service chat độc lập. Không thêm node, edge, nhánh chọn route hay regex. `build_turn_context` tiếp tục giữ profile/facts/trạng thái và transcript gốc; `dialogue_context` là diễn giải ngữ nghĩa riêng, không ghi đè phần đó. Router v9 và semantic recheck đọc cả hai. Q&A formatter, Case QA và câu hỏi tra cứu nhận thêm ngữ cảnh; Planner chỉ nhận diễn giải khi các nguồn thuộc scope business, general chat chỉ nhận khi nguồn thuộc scope general (ngoại trừ message hiện tại chưa được phân loại).

Đầu vào gồm tối đa 16 message gần nhất theo đúng thứ tự USER/ASSISTANT, ID/scope từng message, câu hiện tại nguyên văn, tác vụ đang chờ và semantic checkpoint trước đó. Budget 16.000 ký tự là soft limit: luôn giữ trọn message hiện tại. Các nguồn cũ được checkpoint viện dẫn được đọc lại từ chính conversation, tối đa 32 ID, trích đoạn 1.200 ký tự/nguồn. Model trả `current_goal`, `interpreted_question`, `topic_transition`, `links`, `context_summary`, `corrections`, `open_questions`, `uncertainty`; các ghi nhận và liên kết phải dẫn nguồn được cung cấp. Python kiểm tra schema, ID trong conversation, câu USER hiện tại và chiều thời gian của liên kết; đây không phải kiểm chứng độc lập tính đúng của diễn giải.

Checkpoint version `dialogue-context-v1` và `through_message_id` được lưu trong JSON metadata hiện có sau lượt xử lý thành công, không cần migration. Không lưu lại bản sao source text trong checkpoint. Lượt sau đọc checkpoint cùng các lượt mới để cập nhật mục tiêu/đính chính; không tái sử dụng câu hỏi cũ làm câu hiện tại. Nếu cửa sổ bỏ qua đoạn lịch sử chưa được checkpoint bao phủ, `history_gap=true` được giữ rõ ràng, không coi đó là transcript hoàn chỉnh. ID từ conversation khác, internal message và general message chưa được phép phát bị loại.

Lượt đầu chưa có câu trả lời trước thì trả `no_history`, không gọi model vì chưa có quan hệ lượt thoại để phân tích. Mỗi lượt có lịch sử thêm tối đa một lời gọi LLM, không retry, output tối đa 3.000 token. Timeout, thiếu key hoặc output/schema/provenance lỗi trả `unavailable` rồi dùng raw/deterministic context hiện có. Không đổi facts, pending action, xác nhận hay quyền thực thi; diễn giải câu hỏi chỉ bổ trợ, câu gốc vẫn được giữ nguyên. Semantic memory dùng prompt nên có thể hiểu sai; lịch sử gốc và cơ chế xác thực nghiệp vụ vẫn là nguồn chính.

Nghiên cứu và nguồn sơ cấp: [semantic-conversation-memory-research-2026-10-17.md](semantic-conversation-memory-research-2026-10-17.md).

Kiểm tra mới: **225 regression tests passed**, sau đó **38 targeted tests passed** gồm thêm test giữ trọn câu dài (tổng 226 test khác nhau); **2 integration tests PostgreSQL passed** (rollback dữ liệu giả). Integration đi qua API thật, semantic model giả lập, kiểm tra checkpoint JSON, cập nhật theo lượt, context đi vào router/Q&A và facts/report/pending task giữ nguyên. Model thật phân tích được năm kịch bản giả lập: hỏi thông tin sau hướng dẫn, đính chính loại biên bản, đổi chủ đề, nối tiếp mơ hồ và trợ lý trước đó nhận nhầm đã phê duyệt. Hai câu hỏi thông tin đầu vào chọn `minutes_required_information`, câu đính chính phạm vi chỉ hỏi hướng dẫn vẫn ở `system_help`; một lượt tiếp theo từ checkpoint được phân tích thành công. Kiểm tra bổ sung chọn `general_chat` khi đổi sang hỏi món ăn, chọn `clarify` với câu nối tiếp còn hai cách hiểu, không phát sinh action. Model đôi lúc diễn giải uncertainty rộng hơn chỉ mơ hồ tham chiếu; đây vẫn là output cần đối chiếu câu gốc, không phải ground truth. Kết quả và giới hạn smoke lưu ở `eval/routing/semantic-context-results.json`, không phải accuracy toàn bộ hệ thống.

## Dữ liệu và UI

- Hai nhánh mới là `state_update=preserve`, `task_change=keep`; không ghi facts, thu hồi báo cáo, chuyển trạng thái, gửi phiếu hoặc phát notification nghiệp vụ.
- Lưu scope trên cả USER và ASSISTANT. Context nghiệp vụ lọc social/help/clarification trước khi lấy cửa sổ gần nhất, kể cả transcript fallback. Chỉ casual messages đã được phép phát mới vào cửa sổ general riêng.
- Context Q&A giữ tối đa tám message Q&A gần nhất trong `social_context.help_messages`, tách khỏi facts và summary nghiệp vụ. Chat độc lập cũng lưu `context_scope=system_help`; các message cũ có `kind=system_help` vẫn được nhận diện. Formatter giới hạn turn context 12.000 ký tự và từng message Q&A 2.000 ký tự.
- Dùng snapshot facts để giữ đúng `facts_locked`; `CaseState` khai báo rõ `accepted_keys` và `validation` để LangGraph không bỏ chúng.
- `TurnResponse` bổ sung optional `reply_kind` và `state_update`; frontend giữ cache nghiệp vụ khi phản hồi preserve. Cơ chế hiện chữ dần hiện có tiếp tục dùng sau khi kiểm tra xong output.
- Metadata dùng JSONB messages hiện có, không cần migration. Quyền truy cập, trạng thái cho phép chat và authorization tại API vẫn được giữ.

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `SYSTEM_HELP_ENABLED` | `true` | Bật catalog Q&A; tắt thì node trả thông báo tạm tắt |
| `SYSTEM_HELP_FORMAT_TIMEOUT_SECONDS` | `20` | Timeout bước diễn đạt Q&A, không retry; quá hạn dùng đáp án gốc |
| `DIALOGUE_CONTEXT_TIMEOUT_SECONDS` | `20` | Timeout bước hiểu mạch hội thoại trước router; lỗi dùng context gốc |
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
