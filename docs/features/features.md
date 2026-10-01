# HR Help — Feature và sequence diagram

- **Mã dự án:** P-029
- **Sản phẩm:** HR Help
- **Ngày:** 26/09/2026
- **Trạng thái:** Bản brainstorm bám PRD, Project Brief và schema hiện có

Tài liệu này mô tả các feature cần có để biến khung template thành một ứng dụng xử lý kỷ luật lao động dùng được. Mỗi feature có một sequence diagram chi tiết.

Thành phần dùng chung trong các sơ đồ:

| Thành phần | Vai trò trong luồng |
|---|---|
| HR / Quản lý | Mở hồ sơ, chat, xác nhận fact, đọc đề xuất và lý do giữ lại |
| Pháp chế | Đọc ticket đã đẩy, trên hồ sơ được cấp quyền `REVIEW`, duyệt hoặc từ chối |
| Người ký | Ban hành quyết định. Là người dùng thật, không phải agent |
| Web | Giao diện |
| FastAPI | Kiểm tra quyền, gọi từng sub-agent, ghi database |
| LangGraph | Trích fact, hỏi lại, tra cứu, viết đề xuất, rồi giữ hồ sơ hoặc đẩy ticket |
| PostgreSQL | Hồ sơ, fact, hội thoại, đề xuất, nháp, review, quyết định |
| pgvector | Chunk văn bản và embedding tiền lệ |

## Repo đang có gì

| Lớp | Đã có | Chưa có |
|---|---|---|
| Sản phẩm | PRD: HR nhập tình huống, agent hỏi thêm, đối chiếu luật và nội quy, đề xuất quy trình, pháp chế duyệt, người ban hành quyết định | Giao diện, đăng nhập, màn hình hồ sơ |
| Agent | LangGraph 2 node `analyze` → `respond`, một API `POST /chat` | Làm rõ tình tiết, RAG, trích dẫn, đề xuất, nháp văn bản |
| Dữ liệu | 20 bảng: user, hồ sơ, fact, hội thoại, chính sách theo phiên bản, chunk, đề xuất, trích dẫn, nháp, review, quyết định, tiền lệ | API và service ghi vào các bảng này |
| Kho luật | `scripts/seed_hr_from_legal.py` đổ Bộ luật Lao động, Nghị định 145/2020 và Nghị định 283/2026 vào `policies` → `policy_versions` → `documents` → `document_chunks` (1289 chunk, embedding 1024 chiều, `search_tsv`) | Nội quy công ty. Feature 5 không đọc bốn bảng `legal_*` |

Ba vai trò trong schema là `HR`, `MANAGER`, `LEGAL`. Mức chế tài là khiển trách (`WARNING`), cảnh cáo (`REPRIMAND`), kéo dài nâng lương (`WAGE_POSTPONEMENT`), cách chức (`DEMOTION`), sa thải (`DISMISSAL`) và chấm dứt hợp đồng (`TERMINATION`). Sa thải và chấm dứt hợp đồng là hai căn cứ khác nhau. Agent phải tách chúng.

## Feature nên có

Ưu tiên bám pain point: HR và quản lý mất thời gian tra cứu, dễ áp sai mức, quyết định thiếu căn cứ và không nhất quán giữa các vụ giống nhau.

| # | Feature | Vì sao cần | Bám bảng nào |
|---|---|---|---|
| 1 | Đăng nhập và phân quyền | Hồ sơ kỷ luật là dữ liệu nhạy cảm. Người tạo hồ sơ, người được xem, người được duyệt phải khác nhau | `users`, `case_access` |
| 2 | Mở hồ sơ vụ việc | Mọi tư vấn phải gắn một vụ, một nhân viên, một ngày xảy ra | `cases`, `conversations` |
| 3 | Chat làm rõ tình tiết | Luật không áp được nếu thiếu loại hợp đồng, số ngày nghỉ, đã lập biên bản chưa, đã yêu cầu giải trình chưa | `conversations`, `messages`, `case_facts`, `agent_runs` |
| 4 | Kho văn bản theo ngày hiệu lực | Căn cứ là bản đang có hiệu lực vào `incident_date`, không phải bản đang mở hôm nay | `policies`, `policy_versions`, `documents`, `document_chunks` |
| 5 | Đối chiếu và trích dẫn | Đề xuất không có điều, khoản, điểm thì HR không dùng được | `tool_calls`, `agent_retrievals` |
| 6 | Đề xuất chế tài, quy trình, mức rủi ro | Sub-agent tổng hợp fact và đoạn retrieval thành một đánh giá có trích dẫn, rồi chốt mức khi trích dẫn khớp nguyên văn | `recommendations`, `case_violations` |
| 7 | Soạn nháp và đẩy ticket | Sub-agent đọc `ProposalHandoff` của feature 6. Đủ căn cứ thì soạn nháp và đẩy ticket. Chưa đủ thì giữ đề xuất | `case_drafts`, `recommendations` |
| 8 | Pháp chế duyệt | Chỉ hồ sơ feature 7 đã đẩy sang `PENDING_LEGAL`. Người duyệt, agent không tự duyệt | `reviews` |
| 9 | Ban hành quyết định và lưu tiền lệ | Vụ sau tra được vụ trước đã xử thế nào | `disciplinary_decisions` |
| 10 | Tái phạm cùng nhân viên | Mức kỷ luật phụ thuộc việc đã bị xử trước đó | `cases.employee_code`, `case_violations` |
| 11 | Phân tầng căn cứ | Nghị định 283 là xử phạt của cơ quan nhà nước, không phải mức kỷ luật công ty được quyền áp | `policies.policy_type` |
| 12 | Nhật ký agent | Demo Day cần chứng minh agent đã tra gì, gọi tool gì, tốn bao nhiêu token | `agent_runs`, `tool_calls`, `agent_retrievals` |
| 13 | Dashboard vận hành | PRD có ghi chú dashboard đi muộn. Làm sau khi vòng kỷ luật chạy được | đếm từ `cases` |

Nên làm feature 1–9 cho bản dùng được. Feature 10–12 làm cùng lúc nếu còn sức, vì schema đã chờ sẵn. Dashboard đi muộn để sau.

Ranh giới human-in-the-loop giữ nguyên theo PRD: agent phân tích, cảnh báo, soạn nháp và đẩy ticket khi message của feature 6 đủ căn cứ. Pháp chế phê duyệt. Người có thẩm quyền ban hành quyết định và chịu trách nhiệm.

## Luồng xương sống của một vụ

`cases.status` chỉ nhận các giá trị `OPEN`, `NEED_INFO`, `ANALYZED`, `PENDING_LEGAL`, `APPROVED`, `REJECTED`, `DECIDED`, `CLOSED`.

Feature 6 đóng `ProposalHandoff` sau khi ghi đề xuất. Feature 7 đọc message đó. Chưa đủ căn cứ thì hồ sơ dừng ở `ANALYZED`, recommendation giữ `DRAFT`, không có ticket. Đủ căn cứ thì sub-agent đẩy ticket và hồ sơ sang `PENDING_LEGAL`.

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
    Note over API,AG: Feature 6 đóng ProposalHandoff. Feature 7 đọc message đó
    alt Đề xuất chưa đủ để chuyển pháp chế
        AG->>DB: Giữ recommendations DRAFT và cases ANALYZED
        AG-->>HR: Lý do giữ lại, không có ticket
    else Đủ căn cứ
        AG->>DB: INSERT case_drafts TICKET, status PENDING_REVIEW, case PENDING_LEGAL
        LC->>API: Đọc đề xuất, trích dẫn và ticket
        alt Từ chối
            LC->>API: REJECT kèm comment
            API->>DB: INSERT reviews, case REJECTED
            API-->>HR: Lý do từ chối
            alt HR sửa tình tiết
                HR->>API: Cập nhật fact
                API->>DB: status NEED_INFO, quay lại chat
            else HR giữ fact, viết lại đề xuất
                API->>AG: Sinh recommendation mới
                AG->>DB: Bản REJECTED giữ nguyên, bản mới DRAFT, case ANALYZED
                Note over API,AG: Feature 6 đóng ProposalHandoff mới. Feature 7 xét lại
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

Mọi tư vấn gắn một vụ, một nhân viên và một ngày xảy ra. `incident_date` ghi trên `cases` là mốc feature 5 dùng để chọn `policy_versions` còn hiệu lực. Kho chữ luật hiện có là `BLLD_2019` (`LAW`, từ 2021-01-01), `ND145_2020` (`DECREE`, 2021-02-01 đến 2026-09-09) và `ND283_2026` (`DECREE`, từ 2026-09-10), nằm trên `policies` → `policy_versions` → `documents` → `document_chunks`. Bước mở hồ sơ chỉ ghi `cases` và `conversations`.

`POST /api/v1/cases` chạy node `open` của case graph rồi dừng. Chưa có tin nhắn, chưa có `agent_runs`, chưa rút fact. Client gửi header `X-User-Id`. User phải đang active, role `HR` hoặc `MANAGER`.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    participant API as FastAPI
    participant CG as Case graph
    participant DB as PostgreSQL

    HR->>API: POST /api/v1/cases, header X-User-Id
    Note right of API: body gồm case_code, employee_code, employee_name, description, incident_date
    API->>DB: SELECT users theo X-User-Id
    alt Không có user hoặc is_active false
        API-->>HR: 401
    else Role không phải HR hoặc MANAGER
        API-->>HR: 403
    else Được mở hồ sơ
        API->>CG: ainvoke step = open
        CG->>DB: SELECT cases theo case_code
        alt case_code đã tồn tại
            CG-->>API: 409
            API-->>HR: Mã hồ sơ bị trùng
        else Mã hợp lệ
            CG->>DB: INSERT cases created_by, status OPEN
            CG->>DB: INSERT conversations user_id, case_id, title = case_code, status ACTIVE
            CG-->>API: case_id, conversation_id, status OPEN
            API-->>HR: 201
            Note over CG,DB: incident_date nằm trên cases. Bước này chỉ ghi cases và conversations
        end
    end

    HR->>API: GET /api/v1/cases/id, header X-User-Id
    API->>DB: SELECT cases và conversations ACTIVE
    alt Không phải người tạo
        API-->>HR: 403
    else Hồ sơ không có
        API-->>HR: 404
    else Đúng người tạo
        API-->>HR: Header hồ sơ và conversation_id
    end
```

## 3. Chat làm rõ tình tiết

`POST /api/v1/cases/{id}/messages` chỉ chạy `step = clarify`. Graph đi `extract`, rồi `ask` hoặc dừng. Lượt chat này không vào retrieval và không đề xuất mức.

`case_facts` là phiếu tình tiết hiện tại của hồ sơ, một dòng cho mỗi `fact_key`. Fact đã `confirmed` không bị câu sau đè. Fact chưa xác nhận thì được thay bằng giá trị mới rút từ `cases.description` và các tin `USER`. Chat ghi `confirmed = false` cùng `source_message_id`. HR xác nhận ở `POST /api/v1/cases/{id}/facts/confirm` thì dòng đó thành `confirmed = true`, có `confirmed_by` và `confirmed_at`.

Bộ fact bắt buộc theo loại vụ:

| Loại vụ | `fact_key` |
|---|---|
| Nghỉ không phép `UNAUTHORIZED_ABSENCE` | `contract_type`, `absence_days`, `notice_form`, `minutes_made`, `explanation_requested` |
| Đi muộn `LATE` | `contract_type`, `late_days`, `minutes_made`, `explanation_requested` |
| Chung `GENERAL` | `contract_type`, `violation_summary`, `minutes_made`, `explanation_requested` |

Hồ sơ còn nhận tin khi status là `OPEN`, `NEED_INFO`, `ANALYZED`, hoặc `REJECTED`. Status sau đó trả 409.

Lượt `clarify` đọc và ghi hội thoại với phiếu fact. Cửa đọc của đối chiếu là `document_chunks`, và cửa đó chỉ mở ở feature 5 sau khi fact bắt buộc đã khóa. `legal_documents`, `legal_chunks`, `legal_chunk_references` và `legal_chunk_embeddings` không tham gia lượt chat.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    participant API as FastAPI
    participant CG as Case graph
    participant EX as extract
    participant ASK as ask
    participant DB as PostgreSQL

    HR->>API: POST /api/v1/cases/id/messages, X-User-Id
    API->>DB: SELECT users, cases, conversations ACTIVE
    alt Không được sửa hồ sơ
        API-->>HR: 401, 403, 404 hoặc 409
    else Được chat
        API->>DB: INSERT messages role USER
        API->>DB: INSERT agent_runs RUNNING, model hr-help-rules
        API->>CG: ainvoke step = clarify
        Note over CG,DB: extract và ask chỉ đọc cases, messages, case_facts
        CG->>EX: description + tin USER + case_facts đã lưu
        EX->>EX: Gộp fact, dòng confirmed giữ nguyên
        alt Còn thiếu ô hoặc chưa confirmed
            EX->>ASK: Một câu hỏi hoặc danh sách chờ xác nhận
            ASK-->>API: dừng
            API->>DB: UPSERT case_facts confirmed false
            API->>DB: cases status NEED_INFO
            API->>DB: INSERT messages ASSISTANT, agent_runs SUCCEEDED
            API-->>HR: Câu hỏi, chưa có CaseHandoff
        else Fact bắt buộc đã khóa
            EX-->>API: dừng, không vào retrieve
            API->>DB: INSERT messages ASSISTANT, agent_runs SUCCEEDED
            alt Đã có câu trả lời lưu sẵn
                API-->>HR: Fact đã khóa, câu trả lời đang giữ
            else Chưa có câu trả lời
                API-->>HR: Xác nhận lại để đối chiếu
            end
        end
    end

    HR->>API: POST /api/v1/cases/id/facts/confirm
    API->>CG: ainvoke step = clarify, đọc family và fact hiện có
    alt fact_key không thuộc bộ của vụ
        API-->>HR: 422
    else Payload không đổi và vẫn thiếu fact
        API-->>HR: Câu hỏi tiếp, không ghi thêm
    else Payload không đổi, fact đã khóa, đã có câu trả lời
        API-->>HR: Câu trả lời đang lưu
    else Payload không đổi, fact đã khóa, chưa có câu trả lời
        Note over API,CG: Cùng request chuyển sang feature 5
    else HR sửa hoặc xác nhận
        API->>DB: UPDATE case_facts confirmed, confirmed_by, confirmed_at
        API->>CG: ainvoke step = clarify lần nữa
        alt Vẫn thiếu fact bắt buộc
            API->>DB: cases NEED_INFO, messages ASSISTANT
            API-->>HR: Câu hỏi tiếp
        else Mọi fact đã khóa
            Note over API,CG: Cùng request chuyển sang feature 5
        end
    end
```

`GET /api/v1/cases/{id}/facts` chỉ đọc form tình tiết. Nó chạy `extract` để chiếu giá trị đang đọc được từ mô tả và tin `USER`, không ghi database.

Graph của một lượt chat:

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI
    participant CG as Case graph
    participant EX as extract
    participant ASK as ask
    participant DB as PostgreSQL

    API->>CG: step = clarify
    Note over CG,DB: Chỉ extract, rồi ask hoặc dừng
    CG->>EX: text và stored facts
    alt Còn thiếu fact hoặc chưa confirmed
        EX->>ASK: missing_keys
        ASK-->>CG: question
        CG-->>API: dừng
        API->>DB: case_facts confirmed false, messages ASSISTANT
    else facts_locked
        EX-->>CG: facts và fact_lines
        CG-->>API: dừng
    end
```

## 4. Nạp văn bản và khóa theo ngày hiệu lực

Ba văn bản luật đã nằm trên chuỗi HR: `scripts/seed_hr_from_legal.py` ghi `policies`, `policy_versions`, `documents` (`EMBEDDED`) và `document_chunks` (embedding `mistral-embed` 1024 chiều, `search_tsv`). Sơ đồ dưới đây là API tải file về sau, cho nội quy và văn bản mới. Mỗi chính sách (`LAW`, `DECREE`, `CIRCULAR`, `INTERNAL_RULE`, `PRECEDENT`) có nhiều phiên bản. Hai phiên bản của cùng một chính sách không được chồng ngày hiệu lực. Ràng buộc này đã nằm trong `policy_versions`.

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
            API->>VS: Embed từng chunk, 1024 chiều, mistral-embed
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

Nhánh này chạy trong cùng request `POST /api/v1/cases/{id}/facts/confirm` sau khi mọi fact bắt buộc đã `confirmed` và hồ sơ có `incident_date`. Case graph nhận `step = cite`, đi `extract` → `retrieve` → `handoff`, rồi dừng ở `CaseHandoff`. Feature 6 đọc message đó khi được gắn.

`retrieve` dựng `SearchQuery` từ `cases.description` và `fact_lines`, rồi gọi retrieval graph. Cả ba nhánh và bước mục lục dùng một cửa đọc:

`policies.is_active` → `policy_versions` trạng thái `ACTIVE`, `effective_from` ≤ `incident_date` và `effective_to` tính cả ngày đó (`NULL` nghĩa là còn mở) → `documents.ingest_status` là `CHUNKED` hoặc `EMBEDDED` → `document_chunks`.

Ngày vụ 2026-03-01 gặp `BLLD_2019` và `ND145_2020`. Ngày vụ từ 2026-09-10 gặp `BLLD_2019` và `ND283_2026`. Script `scripts/seed_hr_from_legal.py` ghi `documents.ingest_status = EMBEDDED`. Mỗi chunk có `content`, `article`, `clause`, `point`, `section` (`ARTICLE`, `CLAUSE` hoặc `POINT`), `section_title` là breadcrumb dạng `TEXT`, và `metadata` giữ `article_title` cùng `legal_chunk_id`. `embedding` là `mistral-embed` 1024 chiều. `search_tsv` là `tsvector` sinh sẵn từ `section_title` và `content`, config `simple`, index GIN, migration `0004_document_chunks_tsv`.

`similarity` lấy cosine trên `document_chunks.embedding`. Query chưa có vector thì nhánh này embed `SearchQuery.text`. Vector khác 1024 chiều, thiếu `MISTRAL_API_KEY`, hoặc embed lỗi thì nhánh đó rỗng. `bm25` gọi `ts_rank` trên `search_tsv` của mọi chunk còn hiệu lực và giữ tối đa 8 đoạn. `lexical` là `ILIKE` trên `content`, trần 40 dòng, rồi giữ tối đa 8. Một nhánh lỗi thì kênh đó rỗng, hai nhánh kia vẫn được gộp. `rrf` rồi `rerank` giữ tối đa 8 đoạn, `retrieval = hybrid`. Cả ba rỗng thì `page_index` lấy đầu điều theo cụm neo của family, khớp `content`, `section_title` hoặc `metadata.article_title`. Mục lục cũng không khớp thì `passages` rỗng và `retrieval = empty`.

`missing_internal_rule` trên message là `true` khi không đoạn nào có `policy_type = INTERNAL_RULE`. Bản đổ hiện có luật và nghị định, chưa có nội quy, nên cờ này đúng với kho đang nạp.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR hoặc Quản lý
    participant API as FastAPI
    participant CG as Case graph
    participant EX as extract
    participant RET as retrieve
    participant RG as Retrieval graph
    participant HO as handoff
    participant DB as PostgreSQL

    Note over HR,CG: Tiếp từ feature 3 khi fact đã khóa
    alt Hồ sơ chưa có incident_date
        API-->>HR: 422
    else Có ngày vụ việc
        API->>DB: INSERT messages SYSTEM, fact đã chốt
        API->>DB: INSERT agent_runs RUNNING, model hr-help-rules
        API->>CG: ainvoke step = cite
        CG->>EX: fact đã confirmed
        EX->>EX: fact_lines
        EX->>RET: description, fact_lines, incident_date
        RET->>DB: INSERT tool_calls search_policy RUNNING
        Note right of DB: input gồm query, incident_date, terms, bốn tên nhánh
        RET->>RG: ainvoke RetrievalState
        Note right of DB: policies → policy_versions ACTIVE → documents CHUNKED hoặc EMBEDDED → document_chunks
        par Chunk còn hiệu lực tại incident_date
            RG->>DB: similarity, cosine embedding 1024 chiều
            RG->>DB: bm25, ts_rank trên search_tsv
            RG->>DB: lexical, ILIKE content
        end
        RG->>RG: rrf đọc cả ba kênh
        RG->>RG: rerank, tối đa 8 đoạn
        alt Còn đoạn
            RG-->>RET: hits, retrieval = hybrid
        else Ba nhánh rỗng
            RG->>DB: page_index, đầu điều theo family
            alt Mục lục khớp
                RG-->>RET: hits, retrieval = page_index
            else Mục lục không khớp
                RG-->>RET: hits rỗng, retrieval = empty
            end
        end
        RET->>DB: UPDATE tool_calls SUCCEEDED, output số đoạn và retrieval
        RET->>DB: INSERT agent_retrievals chunk_id, score, rank
        RET->>HO: hits và facts đã khóa
        HO->>HO: đóng CaseHandoff
        Note right of HO: missing_internal_rule khi không có đoạn INTERNAL_RULE
        HO-->>API: dừng
        API->>DB: INSERT messages ASSISTANT, metadata.kind = handoff
        API->>DB: UPDATE agent_runs SUCCEEDED, output_message_id
        API-->>HR: CaseHandoff
    end
```

## 6. Đề xuất chế tài, quy trình, mức rủi ro

Sub-agent này nhận `CaseHandoff` của feature 5. Đầu vào retrieval là `passages` đã lọc theo `incident_date`. Agent không tra thêm văn bản. Mô hình tổng hợp đọc fact đã khóa và các đoạn đó, rồi trả một đánh giá có cấu trúc. Python chỉ giữ mức khi câu trích nằm nguyên văn trong đoạn được nêu, đoạn nội quy có tên mức đó, và có đoạn luật hoặc nghị định hướng dẫn đi kèm. Fact không có trong hồ sơ không được suy ra. Nhiều mức cùng được chứng minh thì chưa chọn.

Chuẩn là `AppliedStandard` trên câu trả lời và trên `ProposalHandoff`:

| Trường | Ý nghĩa |
|---|---|
| `sanction_type` | Đúng một mức đã được trích dẫn đủ, hoặc trống khi đánh giá chưa chốt |
| `process_steps` | Một quy trình: biên bản, giải trình, thời hiệu, người ký |
| `risk_level` | `LOW`, `MEDIUM`, `HIGH`, hoặc `CRITICAL` |
| `aligned` | `true` chỉ khi đã chốt một mức công ty |
| `layers` | Mỗi lớp một vai trò: `basis`, `level` hoặc `open`, `compare`, `excluded` |

| Nguồn trong retrieval | Lớp | Vai trò trong chuẩn |
|---|---|---|
| Luật, nghị định hướng dẫn như Nghị định 145 | `legal_basis` | Căn cứ pháp lý. Điều kiện trong đoạn phải khớp fact. Fact thiếu thì điều kiện là `UNKNOWN` |
| Nội quy còn hiệu lực | `internal_rule` | Mức công ty, chỉ khi đoạn được trích có đúng tên mức và đúng hành vi |
| Tiền lệ | `precedent` | Đối chiếu. Không nâng mức |
| Nghị định xử phạt, gồm Nghị định 283 | `inspection_risk` | Cảnh báo. Không vào `sanction_type` |

Không có mô hình, hoặc trích dẫn không khớp nguyên văn, thì `sanction_type` để trống và rủi ro `HIGH`. Trạng thái `NEED_MORE_FACTS` cũng để trống mức. `MULTIPLE_SUPPORTED` để trống mức, rủi ro `MEDIUM`, feature 7 giữ hồ sơ. Khi còn đúng một mức đã được chứng minh, feature 7 đẩy ticket, hồ sơ sang `PENDING_LEGAL` để pháp chế xem ở feature 8. Chuẩn không bao giờ nhận `TERMINATION`. Agent không chọn mức nặng hơn khi văn bản còn để ngỏ.

Kết quả ghi vào `recommendations`: nhận định, `sanction_type`, `process_steps`, `risk_level`. Mỗi citation giữ `quote`, điều, khoản, điểm và `chunk_id`.

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR
    participant UI as Web
    participant API as FastAPI
    participant AG as Recommend graph
    participant DB as PostgreSQL

    Note over AG: Nhận CaseHandoff từ feature 5
    AG->>AG: Tách passages thành luật, nghị định hướng dẫn, nội quy, tiền lệ, nghị định xử phạt
    AG->>AG: Gộp thành AppliedStandard, một mức và một quy trình
    alt Đánh giá chưa chốt một mức
        AG->>AG: sanction_type trống, aligned false, feature 7 giữ hồ sơ
    else Một mức được trích nguyên văn từ nội quy và từ luật hoặc nghị định
        AG->>AG: Chốt mức đó, quy trình bốn bước
        Note right of AG: Feature 7 đẩy ticket sang PENDING_LEGAL. Không trả TERMINATION
    end
    AG->>DB: INSERT recommendations status DRAFT, rationale, sanction_type, process_steps, risk_level, agent_run_id
    loop Từng đoạn đã dùng trong câu trả lời
        AG->>DB: INSERT recommendation_citations quote, article, clause, point, chunk_id, score
    end
    AG->>DB: UPDATE cases status ANALYZED
    AG->>DB: INSERT messages role ASSISTANT, nội dung đề xuất, metadata.kind = recommendation
    AG->>AG: Đóng ProposalHandoff từ đề xuất vừa ghi
    API-->>UI: ProposalHandoff và đề xuất đã phân tầng
    UI-->>HR: Hiện mức, quy trình, rủi ro, trích dẫn
    Note over AG,HR: Case vẫn ANALYZED, recommendation vẫn DRAFT. Feature 7 đọc message này
```

Feature 6 dừng tại `ProposalHandoff`. Message này là đầu vào duy nhất của feature 7. Feature 6 không tạo `case_drafts`, không ghi `reviews`, và không đổi hồ sơ sang `PENDING_LEGAL`.

## 7. Soạn nháp và đẩy ticket

Sub-agent dispatch đứng sau feature 6. Case graph dừng ở `CaseHandoff`. Recommend graph dừng ở đề xuất đã ghi. Người gọi đóng `ProposalHandoff` rồi gọi dispatch graph. Dispatch graph không phải node của hai graph kia.

Luồng xác nhận fact gọi dispatch một lần, ngay sau khi feature 6 ghi recommendation, trong cùng request. Chat chỉ chạy tới đây khi case graph trả `CaseHandoff`. `agent_runs.model` của lượt này là `hr-help-dispatch`.

Đầu vào duy nhất là `state['proposal']` kiểu `ProposalHandoff`. Sai kiểu thì graph ném `TypeError`. Lượt đó đánh `agent_runs` thành `FAILED`, hồ sơ giữ `ANALYZED`, recommendation giữ `DRAFT`. Graph không mở session, không đọc `messages`, không đọc `case_facts`, không tra `document_chunks`, không gọi model. Cột token để trống.

Feature 6 đã có các cột đề xuất và bốn lớp trích dẫn. `ProposalHandoff` đóng gói đúng các trường đó, cộng phần định danh mà feature 6 đã nhận từ `CaseHandoff`:

| Trường | Nội dung |
|---|---|
| `recommendation_id`, `case_id`, `agent_run_id` | Dòng `recommendations` vừa ghi, trạng thái vẫn `DRAFT` |
| `incident_date`, `employee_name` | Ngày vụ và tên trên hồ sơ đã khóa |
| `family` | `UNAUTHORIZED_ABSENCE`, `LATE`, hoặc `GENERAL` |
| `facts`, `fact_lines` | Chỉ fact đã confirmed |
| `rationale`, `sanction_type`, `process_steps`, `risk_level` | Cột trên `recommendations`. `sanction_type` để trống khi feature 6 chưa chốt mức |
| `missing_internal_rule` | `true` khi không có lớp nội quy |
| `message` | Cột `recommendations.recommendation`, câu HR đọc |
| `legal_basis`, `internal_rule`, `precedent`, `inspection_risk` | Citation đã phân tầng. Mỗi đoạn có `citation_id`, `chunk_id`, `policy_type`, `policy_code`, `policy_name`, `quote`, `article`, `clause`, `point`, `score` |

`process_steps` gồm bốn bước `MINUTES`, `EXPLANATION_REQUEST`, `TIME_LIMIT`, `SIGNER`. Mỗi bước có `code`, `label`, `done`.

FastAPI chỉ gọi graph khi hồ sơ đang `ANALYZED` và recommendation trên message đang `DRAFT`. Một `recommendation_id` chỉ dispatch một lần. Lần sau thấy dòng đó không còn `DRAFT` thì không gọi graph.

Node `gate` đọc message và trả một trong hai hướng. `hold_code` lấy điều kiện đầu tiên khớp:

| Thứ tự | Điều kiện trên message | `hold_code` |
|---|---|---|
| 1 | `sanction_type` là `TERMINATION` | `TERMINATION` |
| 2 | `sanction_type` trống, hoặc không thuộc `WARNING`, `REPRIMAND`, `WAGE_POSTPONEMENT`, `DEMOTION`, `DISMISSAL` | `OPEN_SANCTION` |
| 3 | `risk_level` là `HIGH` hoặc `CRITICAL` | `RISK_HIGH` |
| 4 | `missing_internal_rule` là `true` | `MISSING_INTERNAL_RULE` |
| 5 | `MINUTES` hoặc `EXPLANATION_REQUEST` có `done = false` | `PROCEDURE_OPEN` |

Khớp một dòng thì `disposition = HOLD`. Không khớp dòng nào thì `disposition = SUBMIT`. Node `draft` chỉ chạy ở nhánh `SUBMIT`. Node này chép `sanction_type` từ message vào nháp, không chọn lại mức, không lấy mức từ `precedent` hay `inspection_risk`.

Nhánh giữ lại không ghi `case_drafts`, không ghi `reviews`, không đổi `recommendations.status`, không đổi `cases.status`. FastAPI ghi một tin `ASSISTANT` với `metadata.kind = dispatch_hold` và `metadata.hold_code`. Câu HR đọc là `rationale` trên message. Hồ sơ vẫn `ANALYZED`.

Nhánh đẩy ticket soạn đúng bốn nháp, theo thứ tự `MINUTES`, `EXPLANATION_REQUEST`, `DECISION`, `TICKET`. `title` cắt còn tối đa 255 ký tự. `employee_name` trống thì tiêu đề không gắn tên.

- `MINUTES`: biên bản từ `fact_lines` và các bước đã `done`. Không bịa giờ họp hay người lập biên bản khi fact không có.
- `EXPLANATION_REQUEST`: ghi nhận đã yêu cầu giải trình. Không bịa hạn trả lời khi fact không có.
- `DECISION`: mức và nhận định, trích `legal_basis` và `internal_rule`. Nội dung ghi rõ đây là bản thảo, chưa có `decision_code`, chưa có người ký. `inspection_risk` nằm ở khối cảnh báo. `precedent` chỉ để đối chiếu.
- `TICKET`: phiếu chuyển pháp chế. Gồm nhân viên, ngày vụ, family, fact đã khóa, mức, nhận định, rủi ro, bốn bước thủ tục, và từng citation kèm điều, khoản, điểm, `chunk_id`.

FastAPI ghi trong cùng transaction. `created_by` là `cases.created_by`, không phải user pháp chế và không phải agent. Bốn dòng `case_drafts` để `status = PENDING_REVIEW`, cùng `recommendation_id`. Recommendation chuyển `PENDING_REVIEW`. Hồ sơ chuyển `PENDING_LEGAL`. Tin `ASSISTANT` có `metadata.kind = dispatch_submit`. Thiếu một loại nháp, hoặc trùng loại, thì rollback, `agent_runs` thành `FAILED`, hồ sơ giữ `ANALYZED`, recommendation giữ `DRAFT`.

Sub-agent không cấp `case_access`. Pháp chế chỉ thấy ticket sau khi người tạo hồ sơ đã cấp `REVIEW` ở feature 1. Ticket đã đẩy mà chưa có dòng quyền thì hồ sơ vẫn `PENDING_LEGAL`, hàng chờ của pháp chế trống.

Nháp `DECISION` chỉ là bản thảo cho feature 9. Dispatch graph không ghi `disciplinary_decisions`, không ghi `reviews`, không đặt `APPROVED`, `DECIDED` hay `CLOSED`.

```mermaid
sequenceDiagram
    autonumber
    participant API as FastAPI
    participant DG as Dispatch graph
    participant GT as gate
    participant DR as draft
    participant DB as PostgreSQL
    actor HR as HR

    Note over API,DG: Feature 6 vừa đóng ProposalHandoff, case ANALYZED, recommendation DRAFT
    API->>DB: INSERT agent_runs RUNNING, model hr-help-dispatch
    API->>DG: ainvoke proposal = ProposalHandoff
    alt Message sai kiểu
        DG-->>API: TypeError
        API->>DB: UPDATE agent_runs FAILED
        Note over API,DB: Case giữ ANALYZED, recommendation giữ DRAFT
    else gate trả HOLD
        DG->>GT: Đọc proposal
        GT-->>API: disposition HOLD, hold_code
        API->>DB: INSERT messages ASSISTANT, metadata.kind = dispatch_hold
        API->>DB: UPDATE agent_runs SUCCEEDED
        API-->>HR: Lý do giữ lại, hồ sơ vẫn ANALYZED
    else gate trả SUBMIT
        DG->>GT: Đọc proposal
        GT->>DR: sanction_type đã khóa
        DR-->>API: Bốn nháp MINUTES, EXPLANATION_REQUEST, DECISION, TICKET
        API->>DB: INSERT case_drafts PENDING_REVIEW, created_by là người tạo hồ sơ
        API->>DB: UPDATE recommendations PENDING_REVIEW
        API->>DB: UPDATE cases PENDING_LEGAL
        API->>DB: INSERT messages ASSISTANT, metadata.kind = dispatch_submit
        API->>DB: UPDATE agent_runs SUCCEEDED
        API-->>HR: Ticket đã vào hàng chờ pháp chế
    end
```

## 8. Pháp chế duyệt

Feature 8 là người, không phải graph. Hàng chờ chỉ chứa hồ sơ feature 7 đã đẩy: `cases.status = PENDING_LEGAL` và có `case_drafts` loại `TICKET` trạng thái `PENDING_REVIEW`. User mở hàng chờ phải có role `LEGAL` và một dòng `case_access.access_level = REVIEW` trên hồ sơ đó. Sub-agent không tự duyệt và không tự từ chối.

Gói xem xét lấy từ ticket, recommendation `PENDING_REVIEW`, và `recommendation_citations` đã phân tầng. Gói không gồm fact chưa confirmed và không gồm hội thoại. `inspection_risk` hiện ở khối cảnh báo. `precedent` hiện ở khối đối chiếu. Mức trên gói là `sanction_type` của recommendation, đã khóa từ lúc đẩy ticket.

`POST /cases/id/reviews` nhận `APPROVE` hoặc `REJECT`, và `comment`. Cột `reviews.comment` cho phép trống. `draft_id` của dòng review trỏ vào nháp `TICKET`. Bốn nháp cùng `recommendation_id` đổi status cùng lúc. Trong lúc hồ sơ còn `PENDING_LEGAL`, sửa fact trả `409`.

```mermaid
sequenceDiagram
    autonumber
    actor LC as Pháp chế
    actor HR as HR
    participant UI as Web
    participant API as FastAPI
    participant DB as PostgreSQL

    LC->>UI: Mở hàng chờ
    UI->>API: GET /reviews/queue
    API->>DB: SELECT cases PENDING_LEGAL, có TICKET PENDING_REVIEW, user có access_level REVIEW
    API-->>UI: Danh sách hồ sơ
    LC->>UI: Mở một hồ sơ
    UI->>API: GET /cases/id/review-pack
    API->>DB: Đọc TICKET, recommendation PENDING_REVIEW, citation đã phân tầng
    API-->>UI: Gói để xem xét
    LC->>UI: Chọn APPROVE hoặc REJECT, nhập comment
    UI->>API: POST /cases/id/reviews
    API->>DB: Kiểm tra role LEGAL và case_access REVIEW
    alt Không đủ quyền
        API-->>UI: 403
    else decision APPROVE
        API->>DB: INSERT reviews APPROVE, reviewer_id, recommendation_id, draft_id của TICKET, comment
        API->>DB: UPDATE recommendations APPROVED
        API->>DB: UPDATE bốn case_drafts của recommendation này thành APPROVED
        API->>DB: UPDATE cases APPROVED
        API-->>UI: Đã duyệt
        UI-->>HR: Hồ sơ sẵn sàng để người ký ban hành ở feature 9
    else decision REJECT
        API->>DB: INSERT reviews REJECT, comment
        API->>DB: UPDATE recommendations REJECTED
        API->>DB: UPDATE bốn case_drafts của recommendation này thành REJECTED
        API->>DB: UPDATE cases REJECTED
        API-->>HR: Comment của pháp chế
        Note over LC,DB: Dòng REJECTED và reviews giữ nguyên. Không xóa
        alt HR sửa tình tiết
            HR->>UI: Sửa fact và chat tiếp
            UI->>API: POST messages
            API->>DB: UPDATE cases NEED_INFO
            Note over HR,DB: Recommendation REJECTED giữ nguyên. Quay lại làm rõ, rồi feature 5 và 6
        else HR giữ fact, yêu cầu viết lại
            HR->>UI: Sinh lại đề xuất
            UI->>API: POST /cases/id/recommendations/regenerate
            API->>API: Feature 6 đọc CaseHandoff hiện có
            API->>DB: INSERT recommendation mới DRAFT, case ANALYZED
            Note over API,DB: Bản REJECTED giữ nguyên. Feature 6 đóng ProposalHandoff mới
            API->>API: Feature 7 xét message mới, giữ lại hoặc đẩy ticket
        end
    end
```

Từ chối không xóa đề xuất và không xóa ticket. Dòng `reviews` là dấu vết quyết định và comment. Feature 6 khi ghi bản mới chỉ chuyển các dòng đang `DRAFT` sang `SUPERSEDED`. Dòng `REJECTED` giữ status đó. Bản mới có `recommendation_id` khác. Feature 7 chỉ nhận `ProposalHandoff` của bản mới: chưa đủ căn cứ thì giữ ở `ANALYZED`, đủ căn cứ thì đẩy ticket mới. Comment từ chối nằm trên `reviews` để người đọc. Feature 6 vẫn chỉ đọc `CaseHandoff`, nên comment không đổi mức kỷ luật.

`APPROVE` không ghi `disciplinary_decisions`. Người ký ban hành từ nháp `DECISION` đã `APPROVED` ở feature 9.

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
        API->>VS: Embed precedent_summary, 1024 chiều, mistral-embed
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

Feature 6 đã gộp các nguồn thành một mức. Mục này chỉ xếp citation ra giao diện thành ba nhóm:

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
4. Sub-agent feature 7 đọc `ProposalHandoff`, giữ lại hoặc đẩy ticket, rồi pháp chế duyệt hoặc từ chối.
5. Ban hành quyết định và bật tiền lệ.
6. Thêm nội quy công ty, tái phạm, và tách Nghị định 283 sang lớp cảnh báo.

Bản đó đủ cho Demo Day. Agent phân tích, cảnh báo, soạn nháp, và chỉ đẩy ticket khi đề xuất đủ căn cứ. Người phê duyệt và người ký quyết định chịu trách nhiệm.
