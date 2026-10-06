# P-029 — Flowchart (bản Markdown/Mermaid)

Bản dựng lại từ `P029-flowchart.png` (6744×7406). Mục tiêu: chữ đọc được, sửa được, render trên GitHub / VS Code (cần extension Mermaid Preview).

> Vài cạnh vòng (loop-back) trong ảnh gốc bị rối dây nên ở đây lược giản. Cấu trúc node & luồng chính giữ nguyên.

## Đọc nhanh 4 làn

- **Làn trái — Intake & Clarify:** API vào → mở case, nhận tin nhắn, xác nhận facts → extract → hỏi thêm (ask) hoặc hành động (action) → trả `TurnResponse` về UI.
- **Làn giữa — Retrieval → Handoff → Recommendation:** 3 retriever song song → RRF → rerank → (có hit?) → đóng gói `CaseHandoff` → Recommendation Agent chạy `precedent → recommend → draft` → `ProposalHandoff` → Dispatch Gate.
- **Làn phải trên — Draft & dispatch:** `draft node` sinh 4 loại tài liệu (minutes / explanation / decision draft / legal ticket preview) → preview → HR xác nhận gửi.
- **Làn phải dưới — Legal review & Decision:** Legal duyệt/từ chối → hàng đợi Manager/Signer → ra quyết định → CLOSED → export.

## Sơ đồ

```mermaid
flowchart TD

  %% ================= INTAKE & CLARIFY =================
  subgraph INTAKE["Case intake & clarify — làn trái"]
    EA["Entry API"]
    CGO["Case Graph: open"]
    CC["Create case"]
    CCONV["Create conversation"]
    RCCI["Return case and conversation ids"]
    SUM["Store USER message"]
    CARR["Create agent run: hr-help-rules"]
    CGC["Case Graph: clarify"]
    EX["extract node"]
    CF["Confirm facts"]
    RFP["Recompute fact plan"]
    FL{"Facts locked?"}
    RAE{"Route after extract"}
    ASK["ask node"]
    SACQ["Store ASSISTANT clarify question"]
    AN["action node"]
    AT{"Action type"}
    URAG["Use retrieval as RAG answer"]
    LEA["Load existing assessment"]
    RBM["Return boundary message"]
    SAM["Store ASSISTANT message"]
    RCS["Return current state"]
    RTR["Return TurnResponse"]
    HRU["HR / User"]
    RUI["React UI"]
    FAR["FastAPI Backend"]
    CARRET["Create agent run: hr-help-retrieval"]
    RETRL["Retrieval"]
  end

  %% ================= RETRIEVAL =================
  subgraph RET["Retrieval sub-graph — làn giữa"]
    RG["Retrieval Graph"]
    SIM["Similarity retriever"]
    BM["BM25 retriever"]
    LEX["Lexical retriever"]
    RRF["RRF fusion"]

    subgraph EXPN["expand — duyệt đồ thị dẫn chiếu, hop-1"]
      K1["(1) seed_selector<br/>5 chunk đầu của fused"]
      K2["(2) edge_reader<br/>2 chiều, 2 index"]
      K3["(3) edge_filter<br/>bỏ NULL target / LOW / needs_review"]
      K4["(4) neighbor_hydrate<br/>lấy nội dung + lọc còn hiệu lực<br/>theo incident_date"]
      K5["(5) score_merge<br/>decay x0.6, dedup, cap 12"]
      K6["(6) Provenance<br/>origin = graph + thông tin cạnh"]
    end

    RR["Rerank"]
    HF{"Hits found?"}
    HYB["retrieval = hybrid"]
    PI["Page index fallback"]
    AHF{"Article hits found?"}
    RPI["retrieval = page_index"]
    REM["retrieval = empty"]
  end

  %% ================= HANDOFF =================
  subgraph HND["Handoff — làn giữa"]
    STL["Save tool calls and retrieval logs"]
    HN["handoff node"]
    CH["Create CaseHandoff"]
    SAMH["Store ASSISTANT handoff message"]
    DPW["Downstream parent workflow"]
  end

  %% ================= RECOMMENDATION =================
  subgraph REC["Recommendation & Dispatch Gate — làn giữa"]
    RA["Recommendation Agent"]
    PN["precedent node"]
    RN["recommend node"]
    SDA["Synthesize and draft answer"]
    SRD["Store recommendation DRAFT"]
    SC["Store citations"]
    LCV["Link case violations"]
    SSA["Set case status ANALYZED"]
    CPH["Create ProposalHandoff"]
    DGA["Dispatch Gate Agent"]
    GN["gate node"]
    HC{"Hold condition?"}
    HOLD["HOLD"]
    BHR["Build hold reason"]
    SDHM["Store dispatch hold message"]
    RAWH["Return AnswerView with hold"]
  end

  %% ================= DRAFT & DISPATCH =================
  subgraph DRAFT["Draft & dispatch — làn phải trên"]
    DR["draft node"]
    CRM["Create review minutes"]
    CER["Create explanation request"]
    CDD["Create decision draft"]
    CLTP["Create legal ticket preview"]
    SDPM["Store dispatch preview message"]
    RAVP["Return AnswerView with preview"]
    HCS["HR confirms send"]
  end

  %% ================= LEGAL & DECISION =================
  subgraph LEGAL["Legal review & decision — làn phải dưới"]
    LRW["Legal Review Workflow"]
    LA{"Legal approves?"}
    REJ["Set case status REJECTED"]
    HRO["HR reopens or revises facts"]
    MSQ["Manager or Signer Queue"]
    SID{"Signer issues decision?"}
    RP["Remain pending"]
    CDEC["Create disciplinary decision"]
    CLOSED["Set case status CLOSED"]
    ETA["Export, timeline, audit"]
  end

  %% ----- Intake edges -----
  EA -->|"POST cases"| CGO
  EA -->|"POST case messages"| SUM
  EA -->|"POST confirm facts"| CF
  CGO --> CC --> CCONV --> RCCI
  SUM --> CARR --> CGC
  CF --> RFP --> FL
  CGC --> EX
  EX --> FL
  EX --> RAE
  FL -->|"No"| ASK
  FL -->|"Yes"| RETRL
  RAE -->|"Ready to retrieve"| RETRL
  RAE -->|"Missing facts or conflict"| ASK
  RAE -->|"Special action"| AN
  RAE -->|"Done, no handoff"| RCS
  AN --> AT
  AT -->|"Policy question"| URAG
  AT -->|"Show assessment"| LEA
  AT -->|"Unsupported"| RBM
  ASK --> SACQ --> RTR
  URAG --> SAM
  LEA --> SAM
  RBM --> SAM
  RCS --> SAM
  SAM --> RTR
  RTR --> HRU --> RUI
  RUI --> FAR
  FAR --> EA
  RETRL --> CARRET
  CARRET --> FAR

  %% ----- Retrieval edges -----
  RETRL --> RG
  RG --> SIM
  RG --> BM
  RG --> LEX
  SIM --> RRF
  BM --> RRF
  LEX --> RRF
  RRF --> K1
  K1 --> K2 --> K3 --> K4 --> K5 --> K6
  K6 --> RR
  RR --> HF
  HF -->|"Yes"| HYB
  HF -->|"No"| PI --> AHF
  AHF -->|"Yes"| RPI
  AHF -->|"No"| REM
  HYB --> STL
  RPI --> STL
  REM --> STL

  %% ----- Handoff edges -----
  STL --> HN --> CH --> SAMH --> DPW --> RA

  %% ----- Recommendation edges -----
  RA --> PN --> RN --> SDA --> SRD --> SC --> LCV --> SSA --> CPH --> DGA --> GN --> HC
  HC -->|"Yes"| HOLD --> BHR --> SDHM --> RAWH --> HRO
  HC -->|"No"| DR

  %% ----- Draft & dispatch edges -----
  DR --> CRM
  DR --> CER
  DR --> CDD
  DR --> CLTP
  CRM --> SDPM
  CER --> SDPM
  CDD --> SDPM
  CLTP --> SDPM
  SDPM --> RAVP --> HCS --> LRW

  %% ----- Legal & decision edges -----
  LRW --> LA
  LA -->|"Reject"| REJ --> HRO
  LA -->|"Approve"| MSQ --> SID
  SID -->|"No"| RP
  SID -->|"Yes"| CDEC --> CLOSED --> ETA

  %% ----- Loop-back (lược giản) -----
  HRO -.->|"làm lại"| CGC
  RP -.->|"chờ"| MSQ
```

## Chú thích

- Node **hình thoi `{}`** = điểm quyết định (trong ảnh gốc vẽ nét đứt).
- Nhãn trên mũi tên (`POST cases`, `Yes`, `No`, `Ready to retrieve`, `Reject`, `Approve`…) = điều kiện rẽ nhánh.
- Cạnh nét đứt (`.->`) = vòng lặp/làm lại, đã lược giản so với ảnh gốc.

## GraphRAG — kiến trúc mở rộng (đã vẽ thẳng vào sơ đồ trên)

Sơ đồ lớn ở trên đã tính cả **node `expand`** ngay trong sub-graph Retrieval, nằm giữa
`RRF fusion` và `Rerank` — đó là cách đồ thị dẫn chiếu (`chunk_references`, 599 cạnh,
hiện chưa runtime nào đọc) được đưa vào đường retrieval thật. Bên trong `expand` là 6
khối, cũng vẽ ngay trong sơ đồ đó (sub-graph `expand`).

**Vì sao đặt ở đây (không phải sau Rerank):** Rerank là bước sắp xếp cuối và chốt
danh sách trả ra. Expand chạy sau Rerank thì neighbor mới bị append thô, không được
sắp lại và rơi ngoài top-k đã cắt. Đặt trước Rerank để neighbor được trộn rồi sắp
chung một lượt. Cũng **không làm retriever thứ 4 chạy song song** — graph không có
query riêng, nó phải có kết quả của 3 nhánh kia làm hạt giống.

### Ý tưởng (nói bằng lời)

Text search chỉ tìm chunk có chữ giống câu hỏi. Văn bản luật thì có tính **viện dẫn**:
Nội quy viện dẫn Điều 125 BLLD, hoặc Điều 125 nói "theo khoản 2 Điều 34". Search có
thể tìm ra Nội quy nhưng không bao giờ tìm ra Điều 125 nếu câu hỏi không nhắc tới nó —
trong khi đó lại chính là "căn cứ bắt buộc". Đồ thị đã ghi sẵn 599 quan hệ viện dẫn,
việc còn lại là **đọc nó lúc truy vấn**: tìm được chunk nào liên quan thì lần theo
các mũi tên viện dẫn để kéo thêm điều mà nó dẫn tới.

### Kiến trúc nội bộ khối `expand` (6 khối)

6 khối `(1)…(6)` đã vẽ trong sơ đồ lớn ở trên (sub-graph `expand`). Tóm tắt:

**Mô hình đồ thị:** node = chunk trong `document_chunks`; cạnh = dòng `chunk_references`,
**có hướng** (A viện dẫn B) và **có nhãn** (`rule`, `confidence`). 1377 node / 599 cạnh
→ đồ thị rất thưa (degree ra trung bình < 0.5), hop-1 chỉ thêm vài node, không bùng nổ.
Trừ 63 cạnh external (target NULL), phần duyệt được là ~536 cạnh nội bộ giữa 4 văn bản.

| Khối | Làm gì | Chi tiết đáng chú ý |
|---|---|---|
| (1) seed_selector | Lấy 5 chunk đầu của `fused` làm hạt giống (id + điểm) | Không lấy nhiều: seed rác kéo neighbor rác |
| (2) edge_reader | 2 truy vấn SQL: xuôi `source_chunk_id = ANY(seeds)`, ngược `target_chunk_id = ANY(seeds)` | Dùng index `uq_chunk_references` / `ix_chunk_references_target_source`. **Đọc thẳng SQL**, không cache đồ thị vào RAM — để lọc in-force cùng câu truy vấn và tránh cache trỏ sai sau khi corpus rebuild (UUID sinh mới) |
| (3) edge_filter | Bỏ cạnh `target_chunk_id IS NULL`, `confidence='LOW'`, `needs_review=true` | Lọc tại tầng cạnh là rẻ nhất |
| (4) neighbor_hydrate | Lấy nội dung neighbor, JOIN qua `_candidate_stmt` + `in_force_filter(incident_date)` | **Văn bản được viện dẫn có thể đã hết hiệu lực** tại ngày vi phạm (vd NĐ 145 hết hiệu lực 09/09/2026) → không kéo vào. Đây là lý do graph phải nằm trong pipeline retrieval, không phải công cụ tra cứu riêng |
| (5) score_merge | Gộp cạnh/seed trùng; điểm = `max(điểm seed) × 0.6`; dedup; cap 12; sort ổn định | Hệ số 0.6 = "tin nhưng tin ít hơn kết quả search trực tiếp" → chunk tìm bằng text vẫn thắng khi hòa điểm |
| (6) Provenance | Gắn `origin="graph"` + giữ thông tin cạnh (được điều nào viện dẫn) | Phục vụ audit ledger; `retrieval` mode vẫn là `"hybrid"` |

**Fail-isolation:** lỗi graph → trả `fused` nguyên vẹn. Retrieval không bao giờ chết vì graph.

### Giới hạn hiện tại & hướng phát triển tương lai

**Giới hạn của v1 (cố ý, không phải bug):**
- Đồ thị chỉ có **1 loại cạnh: "viện dẫn"**. Quan hệ "sửa đổi/thay thế/kế thừa" đang ở cấp văn bản (`legal_documents.amended_by`), chưa thành cạnh chunk.
- Chỉ **1 hop**.
- Cạnh `confidence='LOW'` bị **bỏ hẳn**.
- `GRAPH_EDGE_DECAY=0.6`, `GRAPH_SEED_K=5`, `GRAPH_MAX_EXPANSION=12` là số **tune tay**, chưa có cơ sở đo.
- Seed cố định top-5, chưa lọc theo ngưỡng điểm hay đa dạng nguồn.
- 63 cạnh external (target NULL) **không duyệt được** — chưa có chunk cho văn bản ngoài corpus (Luật BHXH, Công đoàn…).
- Rerank vẫn pass-through → neighbor chưa được chấm lại ngữ nghĩa.
- **Chưa có eval (B8)** để so baseline vs graph.

**Hướng phát triển:**
- Mở rộng **loại cạnh** (sửa đổi/thay thế/kế thừa) hoặc dẫn xuất từ `amended_by` → đồ thị giàu ngữ nghĩa hơn.
- **Hop-2 có kiểm soát** / personalized PageRank khi corpus lớn hơn.
- Đưa cạnh **LOW vào với hệ số phạt** thay vì loại bỏ.
- **Tune tham số bằng eval** thay vì đoán (decay, seed_k, cap).
- Gắn **cross-encoder rerank thật** → neighbor được chấm lại, giảm phụ thuộc vào decay.
- **Seed theo ngưỡng/đa dạng** thay vì top-5 cứng.
- Bổ sung chunk cho **văn bản ngoài corpus** để nối các cạnh external.
- **Cache đồ thị** nếu corpus lớn (đánh đổi với độ tươi của dữ liệu).
- Xa hơn: **community detection / global GraphRAG** cho câu hỏi tổng hợp.

> Chi tiết triển khai (thay đổi theo file, tests, verification): `plans/graphrag-hop1-retrieval.md`.
