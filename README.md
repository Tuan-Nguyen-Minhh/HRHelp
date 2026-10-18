# HR Help — Trợ lý chính sách nhân sự (P-029)

**HR Help** là trợ lý AI (human-in-the-loop) hỗ trợ xử lý **hồ sơ kỷ luật lao động**: HR trò chuyện để làm rõ tình tiết vi phạm, hệ thống truy xuất văn bản luật/nghị định/nội quy **còn hiệu lực tại ngày xảy ra vụ việc**, soạn đánh giá tư vấn kèm căn cứ và bản nháp giấy tờ, rồi định tuyến qua **pháp chế duyệt** và **quản lý ban hành quyết định**. Mọi hành động duyệt, ký, đóng hồ sơ do con người có thẩm quyền quyết định — agent chỉ phân tích, tra cứu, tổng hợp và soạn nháp.

> Kiến trúc đầy đủ: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`P029-flowchart.md`](P029-flowchart.md) · flow nghiệp vụ: [`docs/features/features.md`](docs/features/features.md)

## 1. Vấn đề & mục tiêu
Khi có vi phạm nội quy, HR và quản lý thường lúng túng khi áp nội quy cho một tình huống cụ thể: tra cứu luật, nghị định và tiền lệ mất nhiều thời gian, dễ áp sai mức kỷ luật hoặc ra quyết định thiếu căn cứ.

HR Help phân tích tình huống vi phạm, đối chiếu nội quy công ty và quy định pháp luật còn hiệu lực, rồi đề xuất phương án giải quyết kèm trích dẫn căn cứ — vẫn giữ nguyên ranh giới trách nhiệm của con người:
- Rút ngắn thời gian tra cứu và xử lý vụ việc vi phạm.
- Đảm bảo mọi đề xuất kỷ luật minh bạch, nhất quán, có căn cứ pháp lý/nội quy.
- Hỗ trợ quản lý tự tin, chuẩn xác hơn khi ra quyết định.

## 2. Vai trò & ranh giới
| Vai trò | Được làm |
|---|---|
| `HR` | Mở hồ sơ, chat làm rõ, xác nhận fact, đọc báo cáo, gửi phiếu pháp chế, chuyển thẳng quản lý, mở lại hồ sơ bị từ chối |
| `MANAGER` | Xem hàng chờ quản lý, ban hành quyết định nếu có quyền |
| `LEGAL` (pháp chế) | Duyệt/từ chối phiếu; không sửa fact, mức kỷ luật hay citation |
| `SIGNER` | Ban hành quyết định từ đề xuất đã duyệt |
| `ADMIN` | Quản trị hệ thống/người dùng |

**Ranh giới bắt buộc:** agent **không** tự approve/reject/sign/close/delete hay bỏ qua bước pháp chế; không tự ban hành quyết định. Mức kỷ luật trong bản nháp được **sao chép** từ recommendation, không tính lại.

## 3. Luồng nghiệp vụ
1. HR mở hồ sơ → `OPEN`.
2. Chat làm rõ tình tiết → `NEED_INFO`.
3. Trích xuất & xác nhận fact (fact bắt buộc được "khoá").
4. Khi đủ fact và có `incident_date` → truy xuất văn bản còn hiệu lực theo ngày vụ việc.
5. Tổng hợp đánh giá → lưu `recommendations` (DRAFT) → `ANALYZED`.
6. Dispatch gate quyết định HOLD hay tạo preview biên bản/phiếu.
7. HR gửi phiếu cho pháp chế → `PENDING_LEGAL`, hoặc chuyển thẳng quản lý → `APPROVED`.
8. Pháp chế duyệt → `APPROVED`; từ chối → `REJECTED` (bắt buộc kèm lý do).
9. Quản lý/người ký ban hành → `DECIDED` → đóng hồ sơ `CLOSED`.
10. Xuất biên bản/phiếu/quyết định (JSON/Markdown/DOCX).

Trạng thái hồ sơ (`cases.status`): `OPEN → NEED_INFO → ANALYZED → PENDING_LEGAL → APPROVED / REJECTED → DECIDED → CLOSED`. Chat chỉ nhận hồ sơ còn mutable: `OPEN`, `NEED_INFO`, `ANALYZED`, `REJECTED`.

## 4. Kiến trúc
- **Backend** FastAPI (Python 3.11) giữ toàn bộ state workflow, phân quyền, audit, retrieval, lưu recommendation, duyệt, ban hành, thông báo và export.
- **Agent** LangGraph: case graph (intent router + fact planner) và sub-graph retrieval/dispatch.
- **Dữ liệu** PostgreSQL + pgvector (vector 1024 chiều) + BM25 (`search_tsv`).
- **Frontend** Vite + React + TypeScript (React Query), chỉ hiển thị những gì backend đã lưu.

## 5. Multi-agent & pipeline truy xuất
| Agent | Vai trò | File chính |
|---|---|---|
| Case graph | Intent router + trích xuất/làm rõ fact (Python chọn edge, LLM không chọn) | `src/agents/case_graph.py`, `src/features/clarify/model/` |
| Retrieval → `CaseHandoff` | Tìm văn bản còn hiệu lực theo `incident_date`, tạo payload bất biến | `src/features/cite/model/pipeline.py`, `src/agents/handoff.py` |
| Recommendation | Đọc `CaseHandoff`, tổng hợp đánh giá + citation, lưu DRAFT | `src/features/answer/model/answers.py` |
| Dispatch gate | Quyết định HOLD/SUBMIT, chỉ tạo preview draft | `src/features/answer/model/dispatch.py` |

```text
similarity + Okapi BM25 + lexical → RRF (100) → Cohere seed rerank (rerank-v4.0-pro)
  → mở rộng dẫn chiếu (citation graph, hop-1) → facet rerank
  → chọn evidence → tối đa 1 lượt tìm bù → fallback page_index nếu rỗng
```

Xem [`plans/graphrag-hop1-retrieval.md`](plans/graphrag-hop1-retrieval.md), [`docs/retrieval-rerank-implementation.md`](docs/retrieval-rerank-implementation.md).

## 6. Kho tri thức & pipeline dữ liệu
Corpus gồm **4 văn bản** (~1377 chunk, ~599 cạnh dẫn chiếu):

| Mã | Văn bản |
|---|---|
| `BLLD` | Bộ luật Lao động 2019 (hợp nhất 18/VBHN-VPQH) |
| `ND145_2020` | Nghị định 145/2020/NĐ-CP (hướng dẫn điều kiện/quan hệ lao động) |
| `ND283_2026` | Nghị định 283/2026/NĐ-CP (xử phạt hành chính — tầng rủi ro) |
| `NQCT` | Nội quy lao động nội bộ công ty |

Bảng live agent đọc là `document_chunks`; các bảng `legal_*` là bản dựng/build-time. Quy trình 8 bước (docx → md → làm sạch → chunk → metadata → graph → embedding → search): [`data_pipeline_steps/README.md`](data_pipeline_steps/README.md), [`data/README.md`](data/README.md).

## 7. Tech stack
| Lớp | Công nghệ |
|---|---|
| Agent | LangGraph + LangChain 0.3 |
| Backend | FastAPI + Uvicorn (Python 3.11) |
| LLM | DeepSeek / Mistral (`LLM_PROVIDER`, `MODEL_NAME`) |
| Embedding | Mistral `mistral-embed` (1024 chiều) |
| Rerank | Cohere `rerank-v4.0-pro` |
| Database | PostgreSQL 16 + pgvector (+ BM25 qua `search_tsv`) |
| Frontend | Vite + React + TypeScript + TanStack Query + Tailwind |
| DevOps | Docker + GitHub Actions |

## 8. Bắt đầu nhanh
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # điền MISTRAL_API_KEY, COHERE_API_KEY, LLM_PROVIDER...

docker compose up -d db     # Postgres + pgvector
powershell -ExecutionPolicy Bypass -File scripts/restore_handoff.ps1   # nạp corpus (snapshot full)

make run                    # backend: uvicorn src.main:app --reload --port 8000 (Swagger ở /docs)
cd frontend && npm install && npm run dev   # frontend: http://localhost:5173
```

Tài khoản demo (admin/manager/HR/pháp chế) do `scripts/seed_demo_users.py` tạo, chạy sau migration nếu DB chưa có. Chi tiết nạp data: [`handoff/README.md`](handoff/README.md), [`handoff/RUNBOOK_DO_DATA_MOI.md`](handoff/RUNBOOK_DO_DATA_MOI.md).

## 9. API chính
| Chức năng | Endpoint |
|---|---|
| Đăng nhập | `POST /api/v1/auth/login` |
| Hồ sơ | `POST /api/v1/cases`, `GET/PATCH /api/v1/cases/{id}` |
| Chat làm rõ | `POST /api/v1/cases/{id}/messages` |
| Fact | `GET /api/v1/cases/{id}/facts`, `POST /api/v1/cases/{id}/facts/confirm` |
| Đánh giá | `GET /api/v1/cases/{id}/answer` |
| Gửi pháp chế / chuyển quản lý | `POST /api/v1/cases/{id}/ticket`, `POST /api/v1/cases/{id}/escalate` |
| Hàng chờ pháp chế | `GET /api/v1/legal/reviews/queue`, `POST /api/v1/cases/{id}/reviews` |
| Quản lý / quyết định | `GET /api/v1/manager/queue`, `POST /api/v1/cases/{id}/decisions`, `POST /api/v1/cases/{id}/close` |
| Timeline / Export | `GET /api/v1/cases/{id}/timeline`, `GET /api/v1/cases/{id}/export/{kind}` |

Các route thay đổi state nhận header `Idempotency-Key`. Đầy đủ trong [`docs/features/features.md`](docs/features/features.md).

## 10. Đánh giá chất lượng
5 bộ đánh giá trong [`eval/`](eval/README.md):

| Bộ | Đo gì |
|---|---|
| [`eval/retrieval`](eval/retrieval/README.md) | Chất lượng truy xuất (recall, nDCG, evidence) |
| [`eval/routing`](eval/routing/README.md) | Định tuyến intent (10 nhánh) + trích xuất tình tiết |
| [`eval/ingestion`](eval/ingestion/README.md) | Đối chiếu đoạn nguồn với chunk |
| [`eval/case_assessment`](eval/case_assessment/README.md) | Đánh giá RAG bằng RAGAS (4 chỉ số) |
| [`eval/answer_quality`](eval/answer_quality/README.md) | Chất lượng assessment + câu trả lời chat |

## 11. Cấu trúc thư mục
```text
src/
  main.py     Entry point FastAPI (router dưới /api/v1)
  agents/     LangGraph: case_graph.py, handoff.py (CaseHandoff)
  features/   Mỗi feature = controller.py + model/ + schema/ (opencase, clarify, cite,
              answer, assessment, legal_review, decision, export, timeline, ...)
  common/     Auth, access, audit, idempotency, workflow guards
  core/       Settings (config.py), security (RBAC)
  models/     SQLAlchemy models (cases, document_chunks, ...)
frontend/     Vite + React + TS      | eval/        Bộ đánh giá
data/         Corpus                 | handoff/     Snapshot DB để deploy
data_pipeline_steps/  Pipeline       | docs/        Tài liệu nghiệp vụ, research
alembic/versions/     Migrations     | gateG1-chotdetai/  Project Brief + PRD
```

## 12. Tài liệu liên quan
| Tài liệu | Nội dung |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`P029-flowchart.md`](P029-flowchart.md) | Kiến trúc kỹ thuật & flowchart agent |
| [`docs/features/features.md`](docs/features/features.md) | Flow nghiệp vụ, API map, multi-agent |
| [`docs/orchestration-contract.md`](docs/orchestration-contract.md) · [`docs/retrieval-rerank-implementation.md`](docs/retrieval-rerank-implementation.md) | Hợp đồng hội thoại & triển khai retrieval |
| [`plans/graphrag-hop1-retrieval.md`](plans/graphrag-hop1-retrieval.md) | Plan GraphRAG hop-1 |
| [`data_pipeline_steps/README.md`](data_pipeline_steps/README.md) · [`data/README.md`](data/README.md) | Pipeline dữ liệu 8 bước & corpus |
| [`handoff/README.md`](handoff/README.md) · [`handoff/RUNBOOK_DO_DATA_MOI.md`](handoff/RUNBOOK_DO_DATA_MOI.md) | Snapshot DB & runbook nạp data |
| [`eval/README.md`](eval/README.md) · [`design-system/hr-help/MASTER.md`](design-system/hr-help/MASTER.md) | Điều hướng eval & design system |
| [`gateG1-chotdetai/Project_Brief.md`](gateG1-chotdetai/Project_Brief.md) · [`PRD.md`](gateG1-chotdetai/PRD.md) | Định nghĩa dự án (Gate G1) |
| [`frontend/README.md`](frontend/README.md) · [`presentation/README.md`](presentation/README.md) · [`WORKLOG.md`](WORKLOG.md) | Frontend, pitch deck, nhật ký |

## 13. Trạng thái & giới hạn
- **Corpus demo-grade, chưa kiểm chứng nguồn.** Chunk sinh từ `.docx` qua MarkItDown, chưa đối chiếu từng điều với văn bản chính thức → **không phải nguồn pháp lý chính thức**, không dùng để kết luận pháp lý.
- **Đánh giá chưa end-to-end.** Chưa có accuracy/latency đầu-cuối; RAGAS factual correctness của assessment ~0.53; answer-quality đạt 5/10. Toàn bộ nhãn/reference vẫn là **bản nháp chờ chuyên gia HR/pháp chế rà soát**.
- **Mở rộng đồ thị phụ thuộc dữ liệu:** `chunk_references` phải được populate (qua `scripts/copy_chunk_references.py`) mới đo được lợi ích.
- **External research (MCP/web) mặc định tắt** (`EXTERNAL_RESEARCH_ENABLED`); **chưa có live URL/deploy** trong repo và SSE agent chưa phát sự kiện (UI cập nhật theo từng request).
- **Standalone chat** cố ý thiếu node workflow — không thu thập fact, không soạn biên bản; yêu cầu đó được hướng về hồ sơ.
- **Branding cũ còn sót:** `APP_NAME="AI20K Agent"` (`src/core/config.py`) và tiêu đề FastAPI trong `src/main.py` — cần dọn.

## 14. Đội ngũ & License
- **Dự án** P-029 — "HR Help". **Mentor:** Ngô Đình Luân, Trần Hữu Khánh Văn. **Nhóm:** Nhóm P-029.
- **License:** [MIT](LICENSE). Đóng góp theo [`CONTRIBUTING.md`](CONTRIBUTING.md); báo lỗ hổng bảo mật theo [`SECURITY.md`](SECURITY.md).
