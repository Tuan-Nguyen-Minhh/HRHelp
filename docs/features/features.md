# HR Help — Feature và sequence diagram

- **Mã dự án:** P-029
- **Sản phẩm:** HR Help
- **Ngày:** 26/09/2026
- **Trạng thái:** Bản brainstorm bám PRD, Project Brief và schema hiện có

Tài liệu này mô tả các feature cần có để biến khung template thành một ứng dụng xử lý kỷ luật lao động dùng được. Mỗi feature có một sequence diagram chi tiết.

Thành phần dùng chung trong các sơ đồ:

| Thành phần | Vai trò trong luồng |
|---|---|
| HR / Quản lý | Mở hồ sơ, chat, xác nhận fact, chọn nháp, gửi duyệt |
| Pháp chế | Đọc hồ sơ được cấp quyền `REVIEW`, duyệt hoặc từ chối |
| Người ký | Ban hành quyết định. Là người dùng thật, không phải agent |
| Web | Giao diện |
| FastAPI | Kiểm tra quyền, gọi agent, ghi database |
| LangGraph | Trích fact, hỏi lại, tra cứu, viết đề xuất và nháp |
| PostgreSQL | Hồ sơ, fact, hội thoại, đề xuất, nháp, review, quyết định |
| pgvector | Chunk văn bản và embedding tiền lệ |

## Repo đang có gì

| Lớp | Đã có | Chưa có |
|---|---|---|
| Sản phẩm | PRD: HR nhập tình huống, agent hỏi thêm, đối chiếu luật và nội quy, đề xuất quy trình, pháp chế duyệt, người ban hành quyết định | Giao diện, đăng nhập, màn hình hồ sơ |
| Agent | LangGraph 2 node `analyze` → `respond`, một API `POST /chat` | Làm rõ tình tiết, RAG, trích dẫn, đề xuất, nháp văn bản |
| Dữ liệu | 20 bảng: user, hồ sơ, fact, hội thoại, chính sách theo phiên bản, chunk, đề xuất, trích dẫn, nháp, review, quyết định, tiền lệ | API và service ghi vào các bảng này |
| Kho luật | Bộ luật Lao động hợp nhất, Nghị định 145/2020, Nghị định 283/2026 (file trong `data/`) | Nội quy công ty, pipeline nạp tài liệu, lọc đúng ngày xảy ra việc |

Ba vai trò trong schema là `HR`, `MANAGER`, `LEGAL`. Mức chế tài là khiển trách (`WARNING`), cảnh cáo (`REPRIMAND`), kéo dài nâng lương (`WAGE_POSTPONEMENT`), cách chức (`DEMOTION`), sa thải (`DISMISSAL`) và chấm dứt hợp đồng (`TERMINATION`). Sa thải và chấm dứt hợp đồng là hai căn cứ khác nhau. Agent phải tách chúng.

## Feature nên có

Ưu tiên bám pain point: HR và quản lý mất thời gian tra cứu, dễ áp sai mức, quyết định thiếu căn cứ và không nhất quán giữa các vụ giống nhau.

| # | Feature | Vì sao cần | Bám bảng nào |
|---|---|---|---|
| 1 | Đăng nhập và phân quyền | Hồ sơ kỷ luật là dữ liệu nhạy cảm. Người tạo hồ sơ, người được xem, người được duyệt phải khác nhau | `users`, `case_access` |
| 2 | Mở hồ sơ vụ việc | Mọi tư vấn phải gắn một vụ, một nhân viên, một ngày xảy ra | `cases` |
| 3 | Chat làm rõ tình tiết | Luật không áp được nếu thiếu loại hợp đồng, số ngày nghỉ, đã lập biên bản chưa, đã yêu cầu giải trình chưa | `conversations`, `messages`, `case_facts` |
| 4 | Kho văn bản theo ngày hiệu lực | Căn cứ là bản đang có hiệu lực vào `incident_date`, không phải bản đang mở hôm nay | `policies`, `policy_versions`, `documents`, `document_chunks` |
| 5 | Đối chiếu và trích dẫn | Đề xuất không có điều, khoản, điểm thì HR không dùng được | `recommendation_citations` |
| 6 | Đề xuất chế tài, quy trình, mức rủi ro | Đây là đầu ra cốt lõi của PRD | `recommendations`, `case_violations` |
| 7 | Soạn nháp | Biên bản, yêu cầu giải trình, quyết định, ticket. HR chọn có soạn hay chỉ lưu lời tư vấn | `case_drafts` |
| 8 | Pháp chế duyệt | Người kết luận vẫn là người. Agent không tự ban hành | `reviews` |
| 9 | Ban hành quyết định và lưu tiền lệ | Vụ sau tra được vụ trước đã xử thế nào | `disciplinary_decisions` |
| 10 | Tái phạm cùng nhân viên | Mức kỷ luật phụ thuộc việc đã bị xử trước đó | `cases.employee_code`, `case_violations` |
| 11 | Phân tầng căn cứ | Nghị định 283 là xử phạt của cơ quan nhà nước, không phải mức kỷ luật công ty được quyền áp | `policies.policy_type` |
| 12 | Nhật ký agent | Demo Day cần chứng minh agent đã tra gì, gọi tool gì, tốn bao nhiêu token | `agent_runs`, `tool_calls`, `agent_retrievals` |
| 13 | Dashboard vận hành | PRD có ghi chú dashboard đi muộn. Làm sau khi vòng kỷ luật chạy được | đếm từ `cases` |

Nên làm feature 1–9 cho bản dùng được. Feature 10–12 làm cùng lúc nếu còn sức, vì schema đã chờ sẵn. Dashboard đi muộn để sau.

Ranh giới human-in-the-loop giữ nguyên theo PRD: agent phân tích, cảnh báo và soạn nháp. Pháp chế phê duyệt. Người có thẩm quyền ban hành quyết định và chịu trách nhiệm.

## Luồng xương sống của một vụ

`cases.status` chỉ nhận các giá trị `OPEN`, `NEED_INFO`, `ANALYZED`, `PENDING_LEGAL`, `APPROVED`, `REJECTED`, `DECIDED`, `CLOSED`.

Nếu HR chỉ muốn hỏi cho biết và không tạo ticket, hội thoại vẫn lưu, hồ sơ dừng ở `ANALYZED`. Không đẩy sang pháp chế.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    actor LC as Pháp chế
    actor SG as Người ký
    participant API as FastAPI
    participant AG as LangGraph
    participant DB as PostgreSQL

    HR->>API: Tạo hồ sơ, mô tả tình huống, ngày xảy ra
    API->>DB: INSERT cases, status OPEN
    API->>AG: Phân tích tin nhắn đầu tiên
    alt Còn thiếu tình tiết bắt buộc
        AG->>DB: UPSERT case_facts, status NEED_INFO
        AG-->>HR: Hỏi đúng câu còn thiếu
        HR->>API: Trả lời bổ sung
        API->>AG: Trích fact và hỏi tiếp
    else Fact đã được HR xác nhận
        AG->>DB: INSERT recommendation DRAFT và citation
        AG->>DB: UPDATE cases status ANALYZED
        AG-->>HR: Đề xuất mức chế tài, quy trình, rủi ro
    end
    alt HR chỉ muốn tư vấn, không tạo ticket
        HR->>API: Đóng hội thoại
        API->>DB: UPDATE conversations status CLOSED
        Note over HR,DB: Hồ sơ dừng ở ANALYZED
    else HR gửi pháp chế
        HR->>API: Gửi recommendation và draft
        API->>DB: status PENDING_REVIEW và case PENDING_LEGAL
        LC->>API: Đọc fact, trích dẫn, nháp
        alt Từ chối
            LC->>API: REJECT kèm comment
            API->>DB: INSERT reviews, case REJECTED
            API-->>HR: Lý do từ chối
            alt HR sửa tình tiết
                HR->>API: Cập nhật fact
                API->>DB: status NEED_INFO, quay lại chat
            else HR giữ fact, viết lại đề xuất
                API->>AG: Sinh recommendation mới
                AG->>DB: Bản cũ SUPERSEDED, case ANALYZED
            end
        else Duyệt
            LC->>API: APPROVE
            API->>DB: INSERT reviews, case APPROVED
            SG->>API: Ký quyết định
            API->>DB: INSERT disciplinary_decisions, case DECIDED
            opt Đánh dấu tiền lệ
                SG->>API: precedent_summary
                API->>DB: is_precedent true và embedding
            end
            API->>DB: UPDATE cases status CLOSED
        end
    end
```

## 1. Đăng nhập và quyền trên hồ sơ

`HR` và `MANAGER` mở hồ sơ và chat. `LEGAL` không soạn quyết định thay HR. Pháp chế chỉ vào vụ khi được cấp quyền `REVIEW`. Người tạo hồ sơ luôn thấy vụ của mình qua `cases.created_by`. Người khác cần một dòng trong `case_access` với mức `VIEW` hoặc `REVIEW`.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    actor LC as Pháp chế
    participant UI as Web
    participant API as FastAPI
    participant DB as PostgreSQL

    HR->>UI: Nhập email và mật khẩu
    UI->>API: POST /auth/login
    API->>DB: SELECT users theo email
    alt Không có user, sai password_hash, hoặc is_active false
        API-->>UI: 401
        UI-->>HR: Từ chối đăng nhập
    else Hợp lệ
        API-->>UI: Phiên làm việc, user_id, role
        UI-->>HR: Vào danh sách hồ sơ của mình
    end

    Note over HR,DB: Chủ hồ sơ cấp quyền cho pháp chế hoặc người xem
    HR->>UI: Chọn user và mức VIEW hoặc REVIEW
    UI->>API: POST /cases/id/access
    API->>DB: Kiểm tra cases.created_by bằng user đang nhập
    alt Không phải người tạo
        API-->>UI: 403
        UI-->>HR: Không được cấp quyền hồ sơ này
    else Là người tạo
        API->>DB: INSERT case_access case_id, user_id, access_level, granted_by
        API-->>UI: Đã cấp quyền
    end

    LC->>UI: Mở một hồ sơ
    UI->>API: GET /cases/id
    API->>DB: Đọc cases và case_access của user này
    alt user_id bằng created_by
        API-->>UI: Được xem, chat, xác nhận fact, gửi duyệt
    else access_level VIEW
        API-->>UI: Chỉ xem, ẩn nút sửa và nút duyệt
    else role LEGAL và access_level REVIEW
        API-->>UI: Hàng chờ duyệt, nút APPROVE và REJECT
    else Không có dòng case_access
        API-->>UI: 403
        UI-->>LC: Ẩn hồ sơ khỏi danh sách
    end
```

## 2. Mở hồ sơ vụ việc

Mọi tư vấn gắn một vụ, một nhân viên và một ngày xảy ra. `incident_date` là mốc để feature 5 chọn phiên bản văn bản còn hiệu lực.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    participant UI as Web
    participant API as FastAPI
    participant DB as PostgreSQL

    HR->>UI: Mở form hồ sơ mới
    UI->>API: POST /cases
    Note right of API: body gồm case_code, employee_code, employee_name, description, incident_date
    API->>DB: SELECT cases theo case_code
    alt case_code đã tồn tại
        API-->>UI: 409
        UI-->>HR: Mã hồ sơ bị trùng
    else Mã hợp lệ
        API->>DB: INSERT cases created_by, status OPEN
        API->>DB: INSERT conversations user_id, case_id, status ACTIVE
        API-->>UI: case_id và conversation_id
        UI-->>HR: Mở màn chat của hồ sơ, status OPEN
    end
```

## 3. Chat làm rõ tình tiết

Agent không nhảy tới một mức chế tài khi chưa biết loại hợp đồng, đã báo vắng bằng hình thức nào, đã lập biên bản chưa, đã gửi yêu cầu giải trình chưa.

Fact bắt buộc cố định theo loại việc, lưu ở `case_facts` với `fact_key`. Ví dụ nghỉ không phép: `contract_type`, `absence_days`, `notice_form`, `minutes_made`, `explanation_requested`. HR xác nhận thì `confirmed = true`. Chỉ fact đã xác nhận mới được đưa vào đề xuất.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR
    participant UI as Web
    participant API as FastAPI
    participant AG as LangGraph
    participant DB as PostgreSQL

    loop Cho đến khi mọi fact bắt buộc được xác nhận
        HR->>UI: Gửi mô tả hoặc câu trả lời
        UI->>API: POST /cases/id/messages
        API->>DB: INSERT messages role USER, gắn conversation_id
        API->>DB: INSERT agent_runs status RUNNING, message_id
        API->>AG: invoke query, case_id, incident_date, history
        AG->>DB: SELECT case_facts của hồ sơ
        AG->>AG: Trích fact_key và fact_value từ tin nhắn
        AG->>DB: UPSERT case_facts, source_message_id, confirmed false
        alt Còn thiếu fact bắt buộc
            AG->>DB: UPDATE cases status NEED_INFO
            AG->>DB: INSERT messages role ASSISTANT, đúng câu còn thiếu
            AG->>DB: UPDATE agent_runs SUCCEEDED, output_message_id
            API-->>UI: Câu hỏi làm rõ
            UI-->>HR: Hiện câu hỏi, chưa có mức chế tài
        else Đủ key nhưng HR chưa xác nhận
            AG->>DB: INSERT messages role ASSISTANT, danh sách fact chờ xác nhận
            AG->>DB: UPDATE agent_runs SUCCEEDED
            API-->>UI: Form từng fact
            HR->>UI: Xác nhận hoặc sửa giá trị
            UI->>API: POST /cases/id/facts/confirm
            API->>DB: UPDATE case_facts confirmed true, confirmed_by, confirmed_at
        end
    end
    API->>DB: INSERT case_violations violation_type_id, severity, evidence
    API->>AG: Fact đã khóa, bắt đầu đối chiếu văn bản
```

Bên trong LangGraph, một lượt chat đi qua các node sau. Node tra cứu và node đề xuất chỉ chạy sau khi fact đã khóa.

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI
    participant EX as Node trích fact
    participant ASK as Node hỏi lại
    participant RET as Node tra cứu
    participant PRE as Node tiền lệ
    participant REC as Node đề xuất
    participant DB as PostgreSQL

    API->>EX: State gồm tin nhắn, fact cũ, incident_date
    EX->>DB: Đọc và ghi case_facts
    alt Thiếu fact hoặc chưa confirmed
        EX->>ASK: Danh sách key còn thiếu
        ASK->>DB: Ghi câu hỏi vào messages
        ASK-->>API: Dừng graph, chờ HR trả lời
    else Fact đã confirmed
        EX->>RET: Fact khóa và incident_date
        RET->>PRE: Chunk văn bản đã lọc theo ngày
        PRE->>REC: Tiền lệ và số vụ tái phạm
        REC->>DB: Ghi recommendation và citation
        REC-->>API: Câu trả lời cho HR
    end
```

## 4. Nạp văn bản và khóa theo ngày hiệu lực

Ba file trong `data/` mới là bản Markdown thô. Chưa có bước cắt điều khoản, gắn phiên bản, hay embed. Mỗi chính sách (`LAW`, `DECREE`, `CIRCULAR`, `INTERNAL_RULE`, `PRECEDENT`) có nhiều phiên bản. Hai phiên bản của cùng một chính sách không được chồng ngày hiệu lực. Ràng buộc này đã nằm trong `policy_versions`.

Nội quy công ty chưa có trong kho. Không có nội quy thì agent chỉ trích luật, chưa trả lời được mức công ty được phép dùng.

```mermaid
sequenceDiagram
    autonumber
    actor AD as HR hoặc Pháp chế
    participant UI as Web
    participant API as FastAPI
    participant DB as PostgreSQL
    participant VS as pgvector

    AD->>UI: Tải file, chọn policy_type, version, effective_from, effective_to
    UI->>API: POST /policies/id/versions kèm file
    API->>API: Tính content_hash của file
    API->>DB: SELECT documents theo content_hash
    alt File đã nạp
        API-->>UI: 409, trả document_id cũ
    else File mới
        API->>DB: Kiểm tra khoảng ngày của policy_id có chồng bản khác
        alt Chồng effective_from hoặc effective_to
            API-->>UI: 422, yêu cầu sửa khoảng ngày
            UI-->>AD: Từ chối, không ghi version
        else Khoảng ngày hợp lệ
            API->>DB: INSERT policy_versions status ACTIVE
            API->>DB: INSERT documents ingest_status UPLOADED, storage_path, content_hash
            API->>API: Cắt nội dung theo điều, khoản, điểm
            API->>DB: INSERT document_chunks article, clause, point, content
            API->>DB: UPDATE documents ingest_status CHUNKED
            API->>VS: Embed từng chunk, 1536 chiều
            alt Embed lỗi
                API->>DB: UPDATE documents ingest_status FAILED
                API-->>UI: Báo lỗi, cho chạy lại từ chunk chưa có embedding
            else Embed xong
                VS-->>API: Vector từng chunk
                API->>DB: UPDATE document_chunks.embedding
                API->>DB: UPDATE documents ingest_status EMBEDDED
                API-->>UI: policy_version_id và số chunk
                UI-->>AD: Văn bản sẵn sàng để tra cứu
            end
        end
    end
```

## 5. Đối chiếu và trích dẫn

Truy vấn lọc trước theo ngày: chỉ lấy phiên bản có `effective_from <= incident_date` và `effective_to` trống hoặc `effective_to >= incident_date`. Sau đó mới xếp theo độ giống nội dung.

Nghị định 283 chỉ được gắn như căn cứ cảnh báo thanh tra. Nó không đi vào mức kỷ luật nội bộ. Cách tách này làm ở feature 11.

```mermaid
sequenceDiagram
    autonumber
    participant AG as LangGraph
    participant DB as PostgreSQL
    participant VS as pgvector

    AG->>DB: SELECT policy_versions còn hiệu lực tại incident_date
    Note right of DB: effective_from nhỏ hơn hoặc bằng ngày vụ việc, effective_to trống hoặc lớn hơn hoặc bằng ngày đó, status ACTIVE
    DB-->>AG: Danh sách policy_version_id hợp lệ
    AG->>DB: INSERT tool_calls tên search_policy, input là query và incident_date
    AG->>VS: Tìm chunk trong các version hợp lệ
    VS-->>AG: Chunk, điểm similarity, article, clause, point
    loop Từng chunk được giữ lại
        AG->>DB: INSERT agent_retrievals chunk_id, score
        AG->>DB: Giữ quote, article, clause, point để gắn citation ở bước đề xuất
    end
    alt Không có chunk nội quy INTERNAL_RULE
        AG->>AG: Đánh dấu thiếu nội quy, risk sẽ lên HIGH
    else Có cả luật và nội quy
        AG->>AG: Giữ hai nhóm căn cứ riêng
    end
    AG->>DB: UPDATE tool_calls output và thời điểm kết thúc
```

## 6. Đề xuất chế tài, quy trình, mức rủi ro

Kết quả gồm bốn phần, đúng cột trên `recommendations`: nhận định, mức chế tài, các bước thủ tục (`process_steps`), mức rủi ro `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Mỗi câu viện dẫn ghi `quote`, điều, khoản, điểm và `chunk_id`.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR
    participant UI as Web
    participant API as FastAPI
    participant AG as LangGraph
    participant DB as PostgreSQL

    AG->>AG: Đọc fact confirmed, chunk đã lọc, tiền lệ, số lần tái phạm
    alt Thiếu nội quy hoặc thiếu fact
        AG->>AG: Không chốt sanction_type, risk_level HIGH hoặc CRITICAL
    else Đủ căn cứ
        AG->>AG: Chọn một mức trong sáu sanction_type
        Note right of AG: Tách DISMISSAL và TERMINATION, không trộn sa thải với chấm dứt hợp đồng
        AG->>AG: Sinh process_steps gồm biên bản, giải trình, thời hiệu, người ký
    end
    AG->>DB: INSERT recommendations status DRAFT, rationale, sanction_type, process_steps, risk_level, agent_run_id
    loop Từng đoạn đã dùng trong câu trả lời
        AG->>DB: INSERT recommendation_citations quote, article, clause, point, chunk_id, score
    end
    AG->>DB: UPDATE cases status ANALYZED
    AG->>DB: INSERT messages role ASSISTANT, nội dung đề xuất
    API-->>UI: Đề xuất kèm citation đã phân tầng
    UI-->>HR: Hiện mức, quy trình, rủi ro, trích dẫn
    alt HR chỉ muốn lưu tư vấn
        HR->>UI: Đóng, không tạo ticket
        UI->>API: POST /conversations/id/close
        API->>DB: UPDATE conversations status CLOSED
        Note over HR,DB: Case giữ ANALYZED
    else HR muốn chuyển thành hồ sơ xử lý
        HR->>UI: Tạo ticket và các nháp
        UI->>API: Chuyển sang feature soạn nháp
    end
```

## 7. Soạn nháp

Bốn loại nháp đã có trong schema: `MINUTES` (biên bản), `EXPLANATION_REQUEST` (yêu cầu giải trình), `DECISION` (quyết định), `TICKET` (phiếu chuyển pháp chế). Nháp quyết định chỉ là bản thảo. Ban hành thật nằm ở feature 9.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR
    participant UI as Web
    participant API as FastAPI
    participant AG as LangGraph
    participant DB as PostgreSQL

    HR->>UI: Chọn loại nháp MINUTES, EXPLANATION_REQUEST, DECISION hoặc TICKET
    UI->>API: POST /cases/id/drafts
    API->>DB: Đọc case_facts confirmed và recommendation_citations
    API->>AG: Điền nháp từ fact đã khóa và điều khoản đã trích
    AG-->>API: title và content
    API->>DB: INSERT case_drafts status DRAFT, draft_type, recommendation_id, created_by
    API-->>UI: Bản nháp
    UI-->>HR: Mở editor

    HR->>UI: Sửa nội dung
    UI->>API: PATCH /drafts/id
    API->>DB: UPDATE case_drafts.content, status vẫn là DRAFT
    API-->>UI: Đã lưu

    HR->>UI: Gửi pháp chế
    UI->>API: POST /cases/id/submit-review
    API->>DB: UPDATE case_drafts status PENDING_REVIEW
    API->>DB: UPDATE recommendations status PENDING_REVIEW
    API->>DB: UPDATE cases status PENDING_LEGAL
    API-->>UI: Đã vào hàng chờ pháp chế
    UI-->>HR: Hồ sơ chuyển PENDING_LEGAL
```

## 8. Pháp chế duyệt

Một review gắn được cả đề xuất lẫn nháp. Quyết định chỉ có `APPROVE` hoặc `REJECT`, kèm comment. Từ chối không xóa đề xuất cũ. Đề xuất cũ chuyển `SUPERSEDED` khi agent sinh bản mới, để còn dấu vết vì sao bản trước bị loại.

```mermaid
sequenceDiagram
    autonumber
    actor LC as Pháp chế
    actor HR as HR
    participant UI as Web
    participant API as FastAPI
    participant AG as LangGraph
    participant DB as PostgreSQL

    LC->>UI: Mở hàng chờ
    UI->>API: GET /reviews/queue
    API->>DB: SELECT cases status PENDING_LEGAL mà user có access_level REVIEW
    API-->>UI: Danh sách hồ sơ
    LC->>UI: Mở một hồ sơ
    UI->>API: GET /cases/id/review-pack
    API->>DB: Đọc fact confirmed, recommendation, citation, draft
    API-->>UI: Gói để xem xét
    LC->>UI: Chọn APPROVE hoặc REJECT, nhập comment
    UI->>API: POST /cases/id/reviews
    API->>DB: Kiểm tra role LEGAL và case_access REVIEW
    alt Không đủ quyền
        API-->>UI: 403
    else decision APPROVE
        API->>DB: INSERT reviews decision APPROVE, reviewer_id, recommendation_id, draft_id, comment
        API->>DB: UPDATE recommendations status APPROVED
        API->>DB: UPDATE case_drafts status APPROVED
        API->>DB: UPDATE cases status APPROVED
        API-->>UI: Đã duyệt
        UI-->>HR: Hồ sơ sẵn sàng để ký
    else decision REJECT
        API->>DB: INSERT reviews decision REJECT, comment
        API->>DB: UPDATE recommendations status REJECTED
        API->>DB: UPDATE case_drafts status REJECTED
        API->>DB: UPDATE cases status REJECTED
        API-->>HR: Comment của pháp chế
        alt HR sửa tình tiết
            HR->>UI: Sửa fact và chat tiếp
            UI->>API: POST messages
            API->>DB: UPDATE cases status NEED_INFO
            Note over HR,DB: Quay lại feature chat làm rõ
        else HR giữ fact, yêu cầu viết lại
            HR->>UI: Sinh lại đề xuất
            UI->>API: POST /cases/id/recommendations/regenerate
            API->>AG: Giữ fact confirmed, thêm comment từ chối
            AG->>DB: UPDATE recommendation cũ status SUPERSEDED
            AG->>DB: INSERT recommendation mới status DRAFT
            API->>DB: UPDATE cases status ANALYZED
            API-->>HR: Bản đề xuất mới, gửi duyệt lại
        end
    end
```

## 9. Ban hành và tiền lệ

Mỗi hồ sơ chỉ có một quyết định. Người ban hành là người dùng thật (`issued_by`), không phải agent. Muốn vụ này thành tiền lệ thì bắt buộc có `precedent_summary`, rồi embed đoạn tóm tắt đó để vụ sau tìm theo nghĩa.

```mermaid
sequenceDiagram
    autonumber
    actor SG as Người ký
    participant UI as Web
    participant API as FastAPI
    participant DB as PostgreSQL
    participant VS as pgvector

    SG->>UI: Mở hồ sơ status APPROVED và nháp DECISION đã APPROVED
    UI->>API: GET /cases/id/decision-preview
    API->>DB: Đọc draft DECISION, recommendation, citation
    API-->>UI: Bản xem trước, sanction_type khóa theo đề xuất đã duyệt
    SG->>UI: Nhập decision_code, summary, legal_basis, xác nhận ký
    UI->>API: POST /cases/id/decisions
    API->>DB: Kiểm tra chưa có disciplinary_decisions của case_id
    alt Đã có quyết định
        API-->>UI: 409, mỗi hồ sơ chỉ một quyết định
    else Chưa ban hành
        API->>DB: INSERT disciplinary_decisions decision_code, sanction_type, summary, legal_basis, issued_by, issued_at, draft_id
        API->>DB: UPDATE case_drafts status ISSUED
        API->>DB: UPDATE cases status DECIDED
        API-->>UI: Quyết định đã ban hành
    end
    alt Không lấy làm tiền lệ
        SG->>UI: Đóng hồ sơ
        UI->>API: POST /cases/id/close
        API->>DB: UPDATE cases status CLOSED
    else Đánh dấu tiền lệ
        SG->>UI: Nhập precedent_summary
        UI->>API: POST /cases/id/decisions/precedent
        API->>API: Từ chối nếu precedent_summary trống
        API->>VS: Embed precedent_summary, 1536 chiều
        VS-->>API: embedding
        API->>DB: UPDATE disciplinary_decisions is_precedent true, precedent_summary, embedding
        API->>DB: UPDATE cases status CLOSED
        API-->>UI: Tiền lệ sẵn sàng cho vụ sau
    end
```

Vụ sau, feature 5 đọc đúng các dòng `is_precedent = true`.

## 10. Tái phạm

Trước khi chốt mức, agent liệt kê các vụ `DECIDED` hoặc `CLOSED` cùng `employee_code`, cùng `violation_type`, còn trong thời hạn tái phạm theo điều khoản đã trích. Kết quả hiện thành một fact, ví dụ `prior_sanction_count`, để HR xác nhận trước khi nó đi vào đề xuất. Không tự nâng mức chỉ vì embedding thấy vụ na ná.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR
    participant API as FastAPI
    participant AG as LangGraph
    participant DB as PostgreSQL

    AG->>DB: Đọc employee_code và violation_type_id của hồ sơ hiện tại
    AG->>DB: SELECT cases DECIDED hoặc CLOSED cùng employee_code
    AG->>DB: JOIN case_violations và disciplinary_decisions
    alt Không có vụ cũ cùng loại, hoặc đã hết thời hạn tái phạm
        AG->>DB: UPSERT case_facts prior_sanction_count giá trị 0, confirmed false
    else Còn trong thời hạn
        AG->>DB: UPSERT case_facts prior_sanction_count, liệt kê decision_code và issued_at trong fact_value
    end
    AG-->>API: Fact tái phạm chờ HR xác nhận
    API-->>HR: Danh sách vụ cũ, chưa tự nâng mức
    HR->>API: Xác nhận hoặc sửa số lần
    API->>DB: UPDATE case_facts confirmed true, confirmed_by, confirmed_at
    API->>AG: Đưa prior_sanction_count đã khóa vào node đề xuất
```

## 11. Phân tầng căn cứ trong câu trả lời

Mỗi citation mang `policy_type` ra giao diện thành ba nhóm:

- Luật và nghị định hướng dẫn kỷ luật lao động: căn cứ để công ty xử lý.
- Nội quy nội bộ đang hiệu lực đúng ngày: mức cụ thể công ty được phép dùng.
- Nghị định xử phạt hành chính: cảnh báo việc công ty có thể bị phạt nếu làm sai thủ tục. Đây không phải menu chế tài cho HR chọn.

```mermaid
sequenceDiagram
    autonumber
    participant AG as LangGraph
    participant DB as PostgreSQL
    participant API as FastAPI
    participant UI as Web
    actor HR as HR

    AG->>DB: Với mỗi citation, join chunk ra document, policy_version, policy
    loop Từng citation
        alt policy_type LAW hoặc DECREE hướng dẫn kỷ luật
            AG->>AG: Xếp vào nhóm căn cứ công ty được áp
        else policy_type INTERNAL_RULE
            AG->>AG: Xếp vào nhóm mức nội quy đúng ngày
        else policy_type PRECEDENT
            AG->>AG: Xếp vào nhóm vụ đã xử trước đây
        else Nghị định xử phạt hành chính, gồm Nghị định 283
            AG->>AG: Xếp vào nhóm cảnh báo thanh tra, cấm đưa vào sanction_type
        end
    end
    AG->>DB: Lưu recommendation, sanction_type chỉ lấy từ nhóm kỷ luật và nội quy
    API->>API: Tách payload thành legal_basis, internal_rule, precedent, inspection_risk
    API-->>UI: Bốn nhóm riêng
    UI-->>HR: Mức chế tài dùng căn cứ kỷ luật. Cảnh báo thanh tra nằm ở khối rủi ro
```

## 12. Nhật ký agent

Mỗi lượt chat ghi một `agent_run` gắn hội thoại và tin nhắn. Tool tra cứu ghi `tool_calls`. Chunk đã lấy ghi `agent_retrievals`, gồm điểm similarity. Token vào và token ra nằm trên `agent_runs` để chấm Demo Day và để pháp chế xem agent đã dựa vào đoạn nào.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR
    participant API as FastAPI
    participant AG as LangGraph
    participant LLM as LLM
    participant DB as PostgreSQL

    HR->>API: Gửi tin nhắn
    API->>DB: INSERT messages role USER
    API->>DB: INSERT agent_runs status RUNNING, conversation_id, message_id, model, started_at
    API->>AG: invoke
    AG->>DB: INSERT tool_calls trước mỗi bước tra cứu, status đang chạy
    AG->>LLM: Prompt kèm fact và chunk
    LLM-->>AG: Câu trả lời, prompt_tokens, completion_tokens
    AG->>DB: INSERT agent_retrievals cho từng chunk đã đưa vào prompt
    AG->>DB: UPDATE tool_calls output
    alt Graph chạy xong
        AG->>DB: INSERT messages role ASSISTANT
        AG->>DB: UPDATE agent_runs SUCCEEDED, output_message_id, prompt_tokens, completion_tokens, completed_at
        API-->>HR: Câu trả lời
    else Lỗi tool hoặc lỗi LLM
        AG->>DB: UPDATE agent_runs status FAILED, error, completed_at
        API-->>HR: Báo lỗi, hồ sơ giữ nguyên status cũ
    end
```

## 13. Dashboard vận hành

Làm sau khi feature 1–9 chạy. Màn này đếm hồ sơ theo trạng thái, theo mức chế tài, và thời gian từ `OPEN` đến `DECIDED`. Dashboard đi muộn trong ghi chú PRD là một nguồn fact đầu vào (số ngày đi muộn của một nhân viên), chưa phải sản phẩm riêng.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    participant UI as Web
    participant API as FastAPI
    participant DB as PostgreSQL

    HR->>UI: Mở dashboard
    UI->>API: GET /dashboard
    API->>DB: Đếm cases theo status, chỉ hồ sơ user được xem
    API->>DB: Đếm disciplinary_decisions theo sanction_type
    API->>DB: Tính thời gian từ cases.created_at đến issued_at
    API-->>UI: Số liệu đã lọc theo quyền
    UI-->>HR: Bảng trạng thái, cơ cấu mức kỷ luật, thời gian xử lý

    Note over HR,DB: Đi muộn là fact đầu vào, chưa phải màn hình riêng
    HR->>UI: Khi mở hồ sơ đi muộn, nhập số ngày
    UI->>API: POST fact absence_days hoặc late_days
    API->>DB: UPSERT case_facts
    API-->>UI: Fact chờ xác nhận, rồi đi vào luồng đề xuất
```

## Thứ tự làm

1. Đăng nhập, mở hồ sơ, chat lưu `messages` và `case_facts`.
2. Nạp Bộ luật Lao động và Nghị định 145, cắt theo điều khoản, lọc theo `incident_date`.
3. Node đề xuất kèm citation, chưa cần nháp.
4. Nháp biên bản và yêu cầu giải trình, hàng chờ pháp chế, duyệt hoặc từ chối.
5. Ban hành quyết định và bật tiền lệ.
6. Thêm nội quy công ty, tái phạm, và tách Nghị định 283 sang lớp cảnh báo.

Bản đó đủ cho Demo Day. Agent phân tích, cảnh báo, soạn nháp. Người phê duyệt và người ký quyết định chịu trách nhiệm.
