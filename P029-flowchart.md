# P-029 — Current Agent Flowchart

Bản này phản ánh repo hiện tại sau cập nhật orchestrator ngày 16/10/2026 (`intent-router-v5-rule-recheck-social-help`). Giữ cách vẽ, các khối và luồng nghiệp vụ cũ; bổ sung semantic recheck và hai nhánh hội thoại:

- Memory/context được build một lần ở đầu turn: `latest_user_message` + `turn_context`.
- Clarify graph đi qua `intent` router trước khi vào `extract`.
- Router dùng open intent label + closed route enum, cùng route cards mô tả phạm vi, ví dụ và trường hợp loại trừ. Python kiểm tra contract rồi `route_after_intent` chọn edge tương ứng.
- Regex chỉ phát hiện giả thuyết; bất kỳ match nào hoặc mâu thuẫn contract đều yêu cầu LLM kiểm tra lại đúng một lần. Không ghi đè intent bằng keyword, không chọn nhánh theo score.
- Giữ các route nghiệp vụ; thêm `general_chat` và `system_help` trực tiếp sau `route_after_intent`.
- Fact planner hỗ trợ dynamic fact schema và schema lock.
- External research là nhánh optional, gọi MCP/search adapter khi được bật bằng env.

## Đọc Nhanh

```text
POST /cases/{id}/messages
  -> build turn_context + latest_user_message
  -> LangGraph Case Graph
     -> intent router
        -> LLM IntentDecision + route cards
        -> regex hypotheses + contract checks
        -> LLM recheck once if any match / contract conflict
           -> confirmed decision / concrete clarification question
     -> route_after_intent
        -> case_qa / action / extract / disambiguate / general_chat / system_help
```

`POST /cases/{id}/facts/confirm` là endpoint riêng cho thao tác xác nhận fact từ UI/form. Một tin nhắn chat bình thường không đi vào endpoint này.

`text` vẫn được giữ bằng `turn_context` để tương thích với planner cũ, nhưng node mới nên đọc rõ:

```text
latest_user_message = câu user vừa nhập
turn_context        = CASE PROFILE + CASE DESCRIPTION + WORKING FACTS + MEMORY + RECENT_TURNS
```

## Main Flow

```mermaid
flowchart TD

  %% ================= API / ENTRY =================
  subgraph API["FastAPI entrypoints"]
    POST_CASE["POST /cases"]
    POST_MSG["POST /cases/{id}/messages"]
    POST_CONFIRM["POST /cases/{id}/facts/confirm<br/>explicit UI confirm action"]
    LIST_FACTS["GET /cases/{id}/facts"]
    FACTS_VIEW["Return FactListResponse<br/>read-only, no agent turn"]
    OPEN_GRAPH["Case Graph: open"]
    CREATE_CASE["Create case"]
    CREATE_CONV["Create conversation"]
    RETURN_CASE["Return case + conversation ids"]
  end

  %% ================= MESSAGE TURN SETUP =================
  subgraph TURN["Clarify turn setup"]
    STORE_USER["Store USER message"]
    START_RULES_RUN["Create agent run: hr-help-rules"]
    LOAD_CASE["Load mutable case + active conversation"]
    LOAD_FACTS["Load stored facts"]
    BUILD_CONTEXT["build_turn_context once<br/>scope-filtered history<br/>separate side context"]
    STATE_CONTRACT["Graph state contract<br/>latest_user_message<br/>turn_context<br/>text = turn_context<br/>case profile<br/>description<br/>stored facts + status<br/>locked_fact_keys<br/>social_context + pending task"]
  end

  %% ================= CASE GRAPH =================
  subgraph CASE_GRAPH["LangGraph Case Graph — clarify"]
    START["START"]
    ROUTE_ENTRY{"_route_entry"}
    INTENT["intent node<br/>LLM structured IntentDecision<br/>detailed semantic route cards"]
    ROUTE_INTENT{"route_after_intent<br/>Python contract gate<br/>no keyword override"}
    CASE_QA["case_qa node<br/>Case Memory QA"]
    GENERAL_CHAT["general_chat node<br/>Everyday conversation"]
    SYSTEM_HELP["system_help node<br/>Approved system Q&A"]
    DISAMBIG["disambiguate node"]
    EXTRACT["extract node<br/>Fact planner / dynamic schema"]
    ASK["ask node"]
    ACTION["action node"]
    ROUTE_EXTRACT{"route_after_extract"}
    DONE["END / current state"]

    %% ================= INTENT RECHECK =================
    subgraph INTENT_CHECK["Inside intent — semantic recheck"]
      RULE_HYPOTHESES["Regex hypotheses only<br/>rule + match + candidate<br/>no signal overwrite"]
      NEED_RECHECK{"Any rule hit<br/>OR contract conflict?"}
      RECHECK["LLM recheck once<br/>question + context + initial<br/>all rules + route cards"]
      RECHECK_RESULT{"Recheck outcome?"}
      CONFIRMED_INTENT["Confirmed route<br/>initial / candidate / other"]
      CLARIFY_INTENT["Needs clarification<br/>question + original reference"]
      ROUTER_FAILURE["Schema / provider error<br/>preserve + error reply<br/>no planner fallback"]
      FINAL_CONTRACT["Validate route / action<br/>record routing trace<br/>total budget: 60s default"]
    end
  end

  %% ================= INTENT ROUTES =================
  subgraph ROUTES["Closed route enum"]
    R_CASE_QA["case_qa"]
    R_GENERAL["general_chat"]
    R_HELP["system_help"]
    R_FACT["fact_planner"]
    R_POLICY["policy_qa"]
    R_WORKFLOW["workflow_action"]
    R_EXTERNAL["external_research"]
    R_CLARIFY["clarify"]
    R_UNSUPPORTED["unsupported"]
    R_GAP["capability_gap"]
  end

  %% ================= GENERAL CHAT =================
  subgraph GENERAL["General chat — no tools / case facts"]
    CHAT_BUDGET["Flag + actor rate limit<br/>message + safe chat history"]
    CHAT_INPUT{"Input safety check<br/>allow?"}
    CHAT_GENERATE["LLM GeneralReply<br/>natural Vietnamese + humor<br/>safety / authority limits"]
    CHAT_OUTPUT{"Output safety check<br/>allow?"}
    CHAT_SAFE["Approved safe reply<br/>block / uncertain / error<br/>no unchecked draft"]
    CHAT_RELEASE["Release checked answer"]
  end

  %% ================= SYSTEM HELP =================
  subgraph HELP["System help — Q&A catalog"]
    HELP_TOPICS["Resolve help_topic_ids<br/>router + catalog matcher"]
    HELP_CATALOG["12 approved topics<br/>capabilities / authority<br/>workflow / roles / more"]
    HELP_ANSWER["Approved templates<br/>config-aware features<br/>no LLM rewrite / tools"]
  end

  %% ================= SIDE TURN STATE =================
  subgraph SIDE_STATE["Side-turn response / memory"]
    SIDE_STORE["Scope USER + ASSISTANT<br/>general / system_help<br/>released chat history only"]
    SIDE_RETURN["TurnResponse + reply_kind<br/>preserve state / keep task<br/>keep business UI cache"]
  end

  %% ================= CASE QA =================
  subgraph CASEQA["Case QA path"]
    QA_CONTEXT["Use same turn_context<br/>+ structured case snapshot"]
    QA_ANSWER["answer_case_question<br/>no retrieval, no fact extraction"]
    QA_STORE["Store ASSISTANT case answer"]
    QA_RETURN["Return TurnResponse"]
  end

  %% ================= ACTIONS =================
  subgraph ACTIONS["Action path"]
    ACTION_TYPE{"requested_action"}
    POLICY_QA["answer_policy_question"]
    SHOW_ASSESS["show_assessment"]
    EXTERNAL_RESEARCH["external_research"]
    CAP_GAP["capability_gap"]
    UNSUPPORTED["unsupported"]
    ACTION_STORE["Store ASSISTANT message"]
    ACTION_RETURN["Return TurnResponse"]
  end

  %% ================= POLICY QA =================
  subgraph POLICY["Internal Policy QA"]
    POLICY_QUERY["Build SearchQuery from latest_user_message<br/>+ description + facts"]
    POLICY_RETRIEVE["search_policies"]
    POLICY_ANSWER["answer_policy_question<br/>grounded in internal passages"]
  end

  %% ================= EXTERNAL RESEARCH =================
  subgraph EXT["External Research / MCP"]
    EXT_QUERY["ExternalResearchQuery<br/>question = latest_user_message"]
    EXT_TOOL{"Configured provider?"}
    MCP["mcp_http bridge<br/>POST /tools/call"]
    BRAVE["Brave Search API"]
    TAVILY["Tavily API"]
    EXT_DISABLED["disabled / missing config<br/>fail closed"]
    EXT_ANSWER["answer_external_research<br/>mandatory disclaimer<br/>source refs [E1]"]
  end

  %% ================= FACT PLANNER =================
  subgraph FACTS["Fact planning path"]
    PLAN_TURN["plan_turn<br/>LLM dynamic fact schema"]
    APPLY_POLICY["apply_decision<br/>Python validation<br/>schema lock<br/>critical amendment"]
    PROJECT_PLAN["Project ClarifyPlan"]
    STORE_EXTRACTED["Persist extracted facts<br/>pending or confirmed"]
    STORE_QUESTION["Store ASSISTANT clarify question"]
    FACT_RETURN["Return TurnResponse"]
  end

  %% ================= CONFIRM FACTS =================
  subgraph CONFIRM["Explicit confirm facts path"]
    CONFIRM_FACTS["Confirm facts request"]
    RECOMPUTE["Recompute fact plan"]
    CHECK_KEYS["Validate keys against dynamic specs"]
    APPLY_CONFIRM["Write confirmed/pending facts"]
    CONF_LOCKED{"Facts locked?"}
  end

  %% ================= RETRIEVAL =================
  subgraph RET["Internal Retrieval Graph"]
    CREATE_RETR_RUN["Create agent run: hr-help-retrieval"]
    RET_GRAPH["Retrieval Graph<br/>act query + source facets"]
    SIM["Similarity retriever"]
    BM25["BM25 retriever<br/>internal / authority cohorts"]
    LEX["Lexical retriever"]
    RRF["RRF fusion"]
    SEED_RERANK["Cohere rerank-v4.0-pro<br/>select up to 5 seeds"]
    EXPAND["Graph expand: 1 hop<br/>citation neighbors, in-force filter<br/>keep fused pool + provenance"]
    RERANK["Cohere rerank-v4.0-pro<br/>4 facets: internal / authority<br/>conditions / procedure"]
    EVIDENCE_BUDGET["Select whole passages within budget<br/>quality: OK / INCOMPLETE / DEGRADED<br/>record evidence gaps"]
    COVERAGE{"Missing authority/internal?<br/>rerank OK, not retried"}
    SUPPLEMENT["Targeted BM25 for missing layer<br/>at most one retry"]
    OUTLINE_CHECK{"No hits AND no fused candidates?"}
    HITS{"Hits found?"}
    PAGE_INDEX["Page index fallback"]
    ARTICLE_HITS{"Article hits found?"}
    RET_HYBRID["retrieval = hybrid"]
    RET_PAGE["retrieval = page_index"]
    RET_EMPTY["retrieval = empty"]
    SAVE_RETR["Save tool calls + retrieval logs<br/>rankings, provenance, quality, gaps"]
    HANDOFF_NODE["handoff node"]
    CASE_HANDOFF["Create CaseHandoff<br/>facts + passages + heading/version<br/>rerank score + quality + gaps"]
  end

  %% ================= DOWNSTREAM =================
  subgraph DOWNSTREAM["Downstream recommendation + dispatch"]
    STORE_HANDOFF["Store ASSISTANT handoff message"]
    REC_AGENT["Recommendation Agent"]
    PRECEDENT["precedent node"]
    RECOMMEND["recommend node"]
    SOURCE_LAYERS["Split source layers<br/>precedent/admin cannot set sanction"]
    SYNTHESIS_GATE{"Law/internal content found?<br/>mode is not page_index"}
    QUALITY_GATE{"Any DEGRADED passage?"}
    SYNTHESIZE["DeepSeek structured synthesis<br/>general reasoning rubric<br/>300s request / total budget"]
    SYNTHESIS_GUARD["Python evidence guard<br/>quote + heading/body + source type<br/>fact values, AND/OR, conflicts, gaps"]
    RUBRIC_RESULT["Evidence support index 0–100<br/>guarded severity 1–5 or unknown<br/>issuance status + next actions"]
    NO_SYNTHESIS["No content basis for synthesis<br/>no grounded sanction proposal"]
    SYNTHESIS_ERROR["Operational failure: no sanction<br/>RERANK_FAILED / LLM_FAILED<br/>support index = 0"]
    DRAFT_ANSWER["Draft report + chat in Python<br/>level only if can_recommend<br/>proposal separate from issuance"]
    STORE_DRAFT["Store recommendation DRAFT<br/>+ guarded assessment metadata"]
    STORE_CITES["Store citations"]
    LINK_VIOLATIONS["Link case violations"]
    ANALYZED["Set case status ANALYZED"]
    PROPOSAL["Create ProposalHandoff"]
    DISPATCH["Dispatch Gate Agent"]
    GATE["gate node"]
    HOLD_CHECK{"Hold condition?"}
    HOLD["HOLD<br/>store hold reason"]
    DRAFT_NODE["draft node"]
  end

  %% ================= DRAFT / LEGAL / DECISION =================
  subgraph LEGAL["Draft, legal review, decision"]
    MINUTES["Create review minutes"]
    EXPLANATION["Create explanation request"]
    DECISION_DRAFT["Create decision draft"]
    LEGAL_TICKET["Create legal ticket preview"]
    PREVIEW["Store dispatch preview message"]
    HR_SEND["HR confirms send"]
    LEGAL_REVIEW["Legal Review Workflow"]
    LEGAL_APPROVES{"Legal approves?"}
    REJECTED["Set case status REJECTED"]
    MANAGER_QUEUE["Manager / Signer queue"]
    SIGNER_DECIDES{"Signer issues decision?"}
    PENDING["Remain pending"]
    DISCIPLINARY_DECISION["Create disciplinary decision"]
    CLOSED["Set case status CLOSED"]
    EXPORT["Export, timeline, audit"]
  end

  %% ================= API EDGES =================
  POST_CASE --> OPEN_GRAPH --> CREATE_CASE --> CREATE_CONV --> RETURN_CASE
  POST_MSG --> STORE_USER --> START_RULES_RUN --> LOAD_CASE --> LOAD_FACTS --> BUILD_CONTEXT --> STATE_CONTRACT --> START
  LIST_FACTS --> FACTS_VIEW
  POST_CONFIRM --> CONFIRM_FACTS

  %% ================= CASE GRAPH EDGES =================
  START --> ROUTE_ENTRY
  ROUTE_ENTRY -->|"step=open"| OPEN_GRAPH
  ROUTE_ENTRY -->|"step=cite / advance / non-semantic"| EXTRACT
  ROUTE_ENTRY -->|"semantic clarify"| INTENT
  INTENT --> RULE_HYPOTHESES --> NEED_RECHECK
  INTENT -->|"recovery exhausted"| ROUTER_FAILURE
  NEED_RECHECK -->|"No"| FINAL_CONTRACT
  NEED_RECHECK -->|"Yes, even if route agrees"| RECHECK --> RECHECK_RESULT
  RECHECK_RESULT -->|"confirmed"| CONFIRMED_INTENT --> FINAL_CONTRACT
  RECHECK_RESULT -->|"needs_clarification"| CLARIFY_INTENT --> FINAL_CONTRACT
  RECHECK_RESULT -->|"invalid / unavailable"| ROUTER_FAILURE --> FINAL_CONTRACT
  FINAL_CONTRACT --> ROUTE_INTENT

  ROUTE_INTENT -->|"case_qa"| R_CASE_QA --> CASE_QA
  ROUTE_INTENT -->|"general_chat"| R_GENERAL --> GENERAL_CHAT
  ROUTE_INTENT -->|"system_help"| R_HELP --> SYSTEM_HELP
  ROUTE_INTENT -->|"fact_planner"| R_FACT --> EXTRACT
  ROUTE_INTENT -->|"policy_qa"| R_POLICY --> ACTION
  ROUTE_INTENT -->|"workflow_action"| R_WORKFLOW
  R_WORKFLOW -->|"needs planner / workflow facts"| EXTRACT
  R_WORKFLOW -->|"direct action"| ACTION
  ROUTE_INTENT -->|"external_research"| R_EXTERNAL --> ACTION
  ROUTE_INTENT -->|"clarify / cancel / contract or router error"| R_CLARIFY --> DISAMBIG
  ROUTE_INTENT -->|"unsupported"| R_UNSUPPORTED --> ACTION
  ROUTE_INTENT -->|"capability_gap"| R_GAP --> ACTION

  DISAMBIG --> ACTION_STORE
  CASE_QA --> QA_CONTEXT --> QA_ANSWER --> QA_STORE --> QA_RETURN

  %% ================= NEW SIDE BRANCH EDGES =================
  GENERAL_CHAT --> CHAT_BUDGET
  CHAT_BUDGET -->|"enabled + within limit"| CHAT_INPUT
  CHAT_BUDGET -->|"disabled / limited"| CHAT_SAFE
  CHAT_INPUT -->|"Yes"| CHAT_GENERATE --> CHAT_OUTPUT
  CHAT_INPUT -->|"No / uncertain / failure"| CHAT_SAFE
  CHAT_GENERATE -->|"generation failure"| CHAT_SAFE
  CHAT_OUTPUT -->|"Yes"| CHAT_RELEASE --> SIDE_STORE
  CHAT_OUTPUT -->|"No / uncertain / failure"| CHAT_SAFE --> SIDE_STORE
  SYSTEM_HELP --> HELP_TOPICS --> HELP_CATALOG --> HELP_ANSWER --> SIDE_STORE
  SIDE_STORE --> SIDE_RETURN

  %% ================= ACTION EDGES =================
  ACTION --> ACTION_TYPE
  ACTION_TYPE -->|"answer_policy_question"| POLICY_QA
  ACTION_TYPE -->|"show_assessment"| SHOW_ASSESS --> ACTION_STORE
  ACTION_TYPE -->|"external_research"| EXTERNAL_RESEARCH
  ACTION_TYPE -->|"capability_gap"| CAP_GAP --> ACTION_STORE
  ACTION_TYPE -->|"unsupported"| UNSUPPORTED --> ACTION_STORE
  ACTION_STORE --> ACTION_RETURN

  POLICY_QA --> POLICY_QUERY --> POLICY_RETRIEVE --> POLICY_ANSWER --> ACTION_STORE
  EXTERNAL_RESEARCH --> EXT_QUERY --> EXT_TOOL
  EXT_TOOL -->|"mcp_http"| MCP --> EXT_ANSWER
  EXT_TOOL -->|"brave"| BRAVE --> EXT_ANSWER
  EXT_TOOL -->|"tavily"| TAVILY --> EXT_ANSWER
  EXT_TOOL -->|"disabled/missing"| EXT_DISABLED --> EXT_ANSWER
  EXT_ANSWER --> ACTION_STORE

  %% ================= FACT EDGES =================
  EXTRACT --> PLAN_TURN --> APPLY_POLICY --> PROJECT_PLAN --> STORE_EXTRACTED --> ROUTE_EXTRACT
  ROUTE_EXTRACT -->|"conflict / missing / unlocked"| ASK
  ROUTE_EXTRACT -->|"direct action"| ACTION
  ROUTE_EXTRACT -->|"ready to retrieve"| CREATE_RETR_RUN
  ROUTE_EXTRACT -->|"done"| DONE
  ASK --> STORE_QUESTION --> FACT_RETURN

  %% ================= CONFIRM EDGES =================
  CONFIRM_FACTS --> RECOMPUTE --> CHECK_KEYS --> APPLY_CONFIRM --> CONF_LOCKED
  CONF_LOCKED -->|"No"| ASK
  CONF_LOCKED -->|"Yes"| CREATE_RETR_RUN

  %% ================= RETRIEVAL EDGES =================
  CREATE_RETR_RUN --> RET_GRAPH
  RET_GRAPH --> SIM --> RRF
  RET_GRAPH --> BM25 --> RRF
  RET_GRAPH --> LEX --> RRF
  RRF --> SEED_RERANK --> EXPAND --> RERANK --> EVIDENCE_BUDGET --> COVERAGE
  COVERAGE -->|"Yes"| SUPPLEMENT --> RERANK
  COVERAGE -->|"No / already retried"| OUTLINE_CHECK
  OUTLINE_CHECK -->|"Yes"| PAGE_INDEX --> ARTICLE_HITS
  OUTLINE_CHECK -->|"No"| HITS
  HITS -->|"Yes"| RET_HYBRID --> SAVE_RETR
  HITS -->|"No"| RET_EMPTY --> SAVE_RETR
  ARTICLE_HITS -->|"Yes"| RET_PAGE --> SAVE_RETR
  ARTICLE_HITS -->|"No"| RET_EMPTY
  SAVE_RETR --> HANDOFF_NODE --> CASE_HANDOFF --> STORE_HANDOFF --> REC_AGENT

  %% ================= DOWNSTREAM EDGES =================
  REC_AGENT --> PRECEDENT --> RECOMMEND --> SOURCE_LAYERS --> SYNTHESIS_GATE
  SYNTHESIS_GATE -->|"No"| NO_SYNTHESIS --> DRAFT_ANSWER
  SYNTHESIS_GATE -->|"Yes"| QUALITY_GATE
  QUALITY_GATE -->|"Yes"| SYNTHESIS_ERROR --> DRAFT_ANSWER
  QUALITY_GATE -->|"No; INCOMPLETE still checked"| SYNTHESIZE
  SYNTHESIZE -->|"Valid structured response"| SYNTHESIS_GUARD --> RUBRIC_RESULT --> DRAFT_ANSWER
  SYNTHESIZE -->|"Timeout / model or schema failure"| SYNTHESIS_ERROR
  DRAFT_ANSWER --> STORE_DRAFT --> STORE_CITES --> LINK_VIOLATIONS --> ANALYZED --> PROPOSAL --> DISPATCH --> GATE --> HOLD_CHECK
  HOLD_CHECK -->|"Yes"| HOLD --> ACTION_RETURN
  HOLD_CHECK -->|"No"| DRAFT_NODE

  %% ================= LEGAL EDGES =================
  DRAFT_NODE --> MINUTES --> PREVIEW
  DRAFT_NODE --> EXPLANATION --> PREVIEW
  DRAFT_NODE --> DECISION_DRAFT --> PREVIEW
  DRAFT_NODE --> LEGAL_TICKET --> PREVIEW
  PREVIEW --> HR_SEND --> LEGAL_REVIEW --> LEGAL_APPROVES
  LEGAL_APPROVES -->|"Reject"| REJECTED --> BUILD_CONTEXT
  LEGAL_APPROVES -->|"Approve"| MANAGER_QUEUE --> SIGNER_DECIDES
  SIGNER_DECIDES -->|"No"| PENDING
  SIGNER_DECIDES -->|"Yes"| DISCIPLINARY_DECISION --> CLOSED --> EXPORT

  %% Existing PNG palette and drawing style; new sections use matching pastels.
  style API fill:#fcf2ff,stroke:#e5abff,stroke-width:1px
  style TURN fill:#effdfc,stroke:#7fdedb,stroke-width:1px
  style CASE_GRAPH fill:#fff6ed,stroke:#ffc492,stroke-width:1px
  style INTENT_CHECK fill:#fff6ed,stroke:#ffc492,stroke-width:1px
  style ROUTES fill:#effeff,stroke:#6fdddd,stroke-width:1px
  style CASEQA fill:#effff4,stroke:#86dfaa,stroke-width:1px
  style GENERAL fill:#effff4,stroke:#86dfaa,stroke-width:1px
  style HELP fill:#f5f2ff,stroke:#c4b1ff,stroke-width:1px
  style SIDE_STATE fill:#effdfc,stroke:#7fdedb,stroke-width:1px
  style ACTIONS fill:#f5f2ff,stroke:#c4b1ff,stroke-width:1px
  style POLICY fill:#fff0f3,stroke:#ff9aa9,stroke-width:1px
  style EXT fill:#fffde7,stroke:#e8d760,stroke-width:1px
  style FACTS fill:#f0f2ff,stroke:#9aa6ff,stroke-width:1px
  style CONFIRM fill:#f7ffe8,stroke:#a4d94c,stroke-width:1px
  style RET fill:#effaff,stroke:#76caff,stroke-width:1px
  style DOWNSTREAM fill:#fff1f3,stroke:#ff909d,stroke-width:1px
  style LEGAL fill:#fcf3ff,stroke:#df8dff,stroke-width:1px
  classDef default fill:#ffffff,stroke:#33334f,color:#080812,stroke-width:1px;
  linkStyle default stroke:black,stroke-width:1px;
```

## Memory / State Contract

| Field | Nội dung | Dùng bởi |
|---|---|---|
| `latest_user_message` | Tin nhắn user vừa gửi | `intent`, `case_qa`, `policy_qa`, `external_research` |
| `turn_context` | Context compact build một lần từ DB/memory | `intent`, `case_qa`, planner context |
| `text` | Tạm thời bằng `turn_context` để tương thích node cũ | `extract_node`, planner fallback |
| `description` | Mô tả gốc của case | QA, retrieval, answer synthesis |
| `stored` | Stored facts hiện tại | router prompt, fact planner, case QA |
| `locked_fact_keys` | Fact schema đang bị khóa trong lượt pending | dynamic schema guard |
| `social_context` | General history đã được cho phép phát, topic help gần nhất, câu gốc và phản hồi làm rõ | router, general chat, help follow-up, clarification |
| `reply_kind` / `state_update` | Loại phản hồi và chế độ giữ/cập nhật state | lưu metadata và cập nhật UI |

Tin nhắn `general`, `system_help`, `routing_clarification`, `routing_error` được gắn scope trên cả USER và ASSISTANT, lọc khỏi lịch sử nghiệp vụ **trước** khi giới hạn số lượt. Câu gốc và phản hồi làm rõ được đưa lại bằng metadata riêng. Hai nhánh mới không thay facts, báo cáo, trạng thái hay tác vụ đang chờ.

`turn_context` gồm:

```text
CASE PROFILE
CASE DESCRIPTION
WORKING FACTS
SHORT_TERM_MEMORY
PENDING_FACT_KEYS
PENDING_ACTION
LAST_USER_INTENT
RECENT_TURNS
```

## Orchestrator Policy

`intent_node` gọi `route_turn`: LLM phân loại semantic bằng route cards, regex tạo giả thuyết và LLM recheck khi cần. Đây là các bước nội bộ của node `intent`, không phải router mới thay thế graph. `IntentDecision` có cấu trúc:

```text
route: closed enum
intent_label: open label
confidence
capability_needed
requested_action
speech_act / target
help_topic_ids
needs_clarification / clarification_question
requires_fact_planner / requires_internal_retrieval / requires_external_research
task_change / signals / candidates
```

Luồng kiểm tra:

1. Regex trả `rule_id`, `candidate_route`, `matched_text` đã chuẩn hóa; không sửa quyết định semantic hoặc OR tín hiệu vào nó.
2. Có bất kỳ rule hit nào, kể cả cùng nhánh với LLM ban đầu, hoặc có mâu thuẫn route/action/requirements thì recheck **một lần** cho tất cả giả thuyết. Recheck đọc câu gốc, ngữ cảnh, quyết định ban đầu, các match và toàn bộ route cards.
3. Recheck xác nhận nhánh ban đầu, nhánh ứng viên hoặc nhánh hợp lệ khác; nếu chưa rõ thì tạo câu hỏi cụ thể, chuyển `disambiguate` và giữ câu gốc cho lượt sau.
4. Python kiểm tra schema và contract trước khi chọn edge. Ví dụ: `system_help` không được kèm `send_to_legal`; nhánh hội thoại phải `task_change=keep` và không yêu cầu retrieval/fact planner. Đây là kiểm tra tính nhất quán, không chứng minh hiểu đúng ý nghĩa 100%.

`route_after_intent` giữ vai trò chọn edge từ quyết định cuối đã kiểm tra:

| Route | Node tiếp theo |
|---|---|
| `case_qa` | `case_qa_node` |
| `general_chat` | `general_chat_node -> END` |
| `system_help` | `system_help_node -> END` |
| `fact_planner` | `extract_node` |
| `policy_qa` | `action_node -> answer_policy_question` |
| `workflow_action` | `action_node` hoặc `extract_node` nếu cần fact |
| `external_research` | `action_node -> external_research` |
| `clarify` | `disambiguate_node` |
| `unsupported` | `action_node -> boundary message` |
| `capability_gap` | `action_node -> capability gap message + log` |

Fallback và trace:

- Thiếu API, timeout, lỗi provider/schema sau ngân sách phục hồi: `disambiguate` báo lỗi xử lý và giữ state, không tự chuyển `extract`. Initial parsing có phục hồi giới hạn; semantic recheck tối đa một lần; tổng ngân sách mặc định 60 giây.
- Mơ hồ semantic: hỏi lại bằng câu hỏi của LLM; lỗi kỹ thuật không được trình bày thành mơ hồ của người dùng. Explicit cancel cũng đi qua `disambiguate` để xác nhận dừng tác vụ.
- `confidence` và candidate scores chỉ dùng theo dõi, không chọn edge theo điểm cao nhất. Không có keyword override.
- Trace lưu initial/final route, rule IDs, route ứng viên và recheck status. Không đảm bảo điều hướng đúng 100%; bộ eval/regression theo dõi sai lệch thực tế.

## Hai nhánh mới

`general_chat`: chào hỏi, trò chuyện đời thường, gợi ý món ăn thông thường. Dùng prompt tiếng Việt tự nhiên, hài hước vừa phải; không giả có quyền quyết định hoặc đã thao tác hồ sơ. Luồng input safety → LLM sinh → output safety; chỉ phát câu trả lời sau kiểm tra, lỗi/không chắc dùng mẫu an toàn. Các safety checks dùng prompt phân loại riêng trên cùng provider, không phải classifier độc lập. Không bind tools, không đưa case profile/facts/report vào prompt; chỉ dùng latest message và tối đa 8 casual messages đã được phép phát. Có feature flag, timeout mỗi bước và rate limit theo actor/worker.

`system_help`: câu hỏi về khả năng, giới hạn quyền hạn và cách dùng hệ thống. Router semantic chọn topic; matcher trong node hỗ trợ catalog Q&A 12 nhóm: giới thiệu, khả năng, quyền hạn, bắt đầu, workflow, biên bản, vai trò, trả lại hồ sơ, nguồn, độ tin cậy, riêng tư và trò chuyện. Kết hợp tối đa 3 topic bằng mẫu đã duyệt, không dùng LLM viết lại; thông tin chức năng phụ thuộc cấu hình thực tế.

Cả hai kết thúc lượt với `state_update=preserve`, `task_change=keep`, lưu hội thoại có scope và giữ cache nghiệp vụ trên frontend. General chat phải kiểm tra xong output trước khi phát; hiệu ứng hiện chữ dần trên UI không phải streaming token chưa kiểm tra từ provider.

Chi tiết triển khai và kiểm chứng: [orchestrator-social-implementation.md](docs/orchestrator-social-implementation.md).

## External Research Config

External research mặc định tắt. Bật bằng `.env`:

```env
EXTERNAL_RESEARCH_ENABLED=true
EXTERNAL_RESEARCH_PROVIDER=mcp_http
EXTERNAL_RESEARCH_MCP_URL=http://localhost:xxxx
EXTERNAL_RESEARCH_MCP_TOOL_NAME=web_search
EXTERNAL_RESEARCH_ALLOWED_DOMAINS=chinhphu.vn,molisa.gov.vn,vbpl.vn
```

Hoặc dùng direct provider:

```env
EXTERNAL_RESEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=...

EXTERNAL_RESEARCH_PROVIDER=tavily
TAVILY_API_KEY=...
```

Mọi câu trả lời external phải có disclaimer rằng đây là nguồn ngoài, chỉ tham khảo, không chắc chắn 100%, không thay thế tư vấn pháp lý/chuyên môn.
