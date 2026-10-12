# Agent gap analysis and improvement plan

Tai lieu nay ghi lai cac diem yeu hien tai cua luong agent va de xuat huong cai thien de teammate co the tach task implement. Trong boi canh he thong HR/legal, agent khong nen tu ra quyet dinh thay nguoi co tham quyen; agent chi lam ro tinh tiet, truy xuat can cu, tong hop rui ro va soan thao de con nguoi xac nhan.

## 1. Tom tat van de

Hien tai luong agent co 2 diem han che lon:

1. Fact cua message dang bi rang buoc vao catalog hardcode.
2. Retrieval moi dung internal data, chua co co che external research/MCP cho cau hoi bo sung khi internal data khong du.

Ngoai ra, can bo sung them guardrail ve source priority, audit, citation, effective date, high-risk legal escalation va evaluation set.

## 2. Diem yeu: fact extraction dang qua cung

### Hien trang

Fact schema hien dang duoc dinh nghia cung trong `src/features/clarify/model/catalog.py`:

- `UNAUTHORIZED_ABSENCE`
- `LATE`
- `GENERAL`

Moi family co mot bo fact bat buoc co dinh, vi du:

- `contract_type`
- `absence_days`
- `notice_form`
- `minutes_made`
- `explanation_requested`
- `violation_summary`

He thong da co semantic planner, nhung planner van bi ep vao schema co dinh:

- `CaseFamily` chi cho phep cac family trong catalog.
- `ExtractedFact.key` chi hop le neu nam trong `catalog_keys()`.
- `apply_decision()` loai bo key ngoai catalog.
- `required_specs(family)` quyet dinh fact nao la bat buoc.

Vi vay LLM chi dang giup doc message tot hon trong mot khung rat hep. No chua duoc phep phan tich dong rang mot vu viec moi can nhung fact nao.

### Rui ro

- Khong cover du cac case thuc te nhu quan roi, gian lan, xung dot loi ich, tiet lo du lieu, tranh chap tien luong, tai nan lao dong, don phuong cham dut hop dong, khiu nai noi bo.
- Agent co the hoi thieu fact quan trong vi catalog khong co key do.
- Agent co the hoi thua fact khong lien quan vi family bi classify sai.
- Khi user mo ta vu viec phuc tap, he thong van co xu huong ep ve `GENERAL`, lam mat cau truc nghiep vu.
- Downstream retrieval/recommendation nhan bo fact ngheo, dan den can cu yeu hoac de xuat khong du an toan.

## 3. De xuat: dynamic fact schema co guard

Khong nen bo het catalog hien tai. Nen bien catalog thanh template/fallback, dong thoi them mot tang `Fact Schema Planner`.

### Luong moi de xuat

```text
User message
  -> classify intent
  -> Fact Schema Planner
  -> Python/schema validator
  -> Fact Extractor theo schema da duoc chap nhan
  -> HR confirm/edit/add fact
  -> lock confirmed facts
  -> retrieval/recommendation
```

### Fact Schema Planner

Planner doc message, stored facts, mo ta case va policy context neu co, roi de xuat schema dong:

```json
{
  "case_family": "harassment | absence | performance | wage | conflict_of_interest | safety | data_leak | general",
  "family_confidence": 0.82,
  "required_facts": [
    {
      "key": "incident_time",
      "label": "Thoi diem xay ra vu viec",
      "question": "Vu viec xay ra vao ngay nao hoac khoang thoi gian nao?",
      "type": "date_or_range",
      "required": true,
      "reason": "Can xac dinh van ban ap dung va thoi hieu xu ly.",
      "source": "ai_generated"
    }
  ],
  "optional_facts": [],
  "risk_flags": [
    {
      "code": "LEGAL_REVIEW_RECOMMENDED",
      "reason": "Vu viec co kha nang phat sinh tranh chap."
    }
  ]
}
```

### Validator bat buoc

LLM chi duoc de xuat schema. Python phai validate truoc khi dung:

- `key` phai theo format an toan: lowercase snake_case, gioi han do dai.
- Khong cho key trung nhau.
- Khong cho key la ket luan phap ly, vi du `employee_is_guilty`, `should_dismiss`.
- `type` phai nam trong whitelist: `text`, `boolean`, `date`, `date_or_range`, `number`, `enum`, `money`, `person`, `document_ref`.
- `question` khong duoc chua instruction dieu khien agent.
- `reason` phai giai thich duoc vi sao fact can cho legal/procedure/retrieval.
- Neu confidence thap, khong lock schema; hoi nguoi dung xac nhan loai vu viec truoc.

### HR/user control

UI/API nen cho HR:

- Sua gia tri fact.
- Them fact thu cong.
- Danh dau `unknown` / `not_available`.
- Xoa fact khong lien quan.
- Yeu cau AI phan tich lai schema khi mo ta vu viec thay doi.

### Data model de xuat

Co the them bang moi hoac JSONB tuy muc do can audit.

Option A - bang rieng:

- `case_fact_requirements`
  - `id`
  - `case_id`
  - `fact_key`
  - `label`
  - `question`
  - `type`
  - `required`
  - `reason`
  - `source`
  - `status`
  - `created_at`

Tiep tuc dung `case_facts` de luu value/confirmation.

Option B - JSONB nhanh hon:

- Them `fact_schema` vao case memory/conversation memory.
- Van giu `case_facts` cho cac value da xac nhan.

Neu can audit nghiem tuc, uu tien Option A.

## 4. Diem yeu: retrieval moi dung internal data

### Hien trang

`src/features/cite/model/search.py` chay retrieval noi bo tren policy/document chunks:

- similarity
- bm25
- lexical
- page_index

Day la dung cho cau hoi noi bo va can cu policy cong ty, nhung chua du cho cau hoi bo sung, vi du:

- "Neu xay ra kien tung thi HR nen xu ly nhu nao?"
- "Quy trinh tranh chap lao dong hien hanh ra sao?"
- "Neu noi quy cong ty khong noi ro thi can can cu van ban nao?"

### Nguyen tac moi

External MCP/tool research chi la option bo sung, khong phai mac dinh.

Source priority:

1. Internal data truoc.
2. Neu internal du can cu, khong goi external.
3. Neu internal rong/yeu/thieu hoac cau hoi ro rang can kien thuc ngoai, moi can nhac external MCP.
4. External research khong duoc override internal policy.
5. External research khong duoc dung de tu dong chot ky luat/cham dut hop dong.

### Khi nao duoc goi external MCP

Chi goi external khi thoa mot trong cac dieu kien:

- Internal retrieval khong tim thay can cu phu hop.
- Cau hoi co tinh bo sung ngoai noi bo, khong phai hanh dong workflow.
- Cau hoi can van ban hien hanh, quy trinh tranh chap, litigation, government guidance, court/labor practice.
- User hoi truc tiep ve "luat hien hanh", "kien tung", "tranh chap", "co quan nha nuoc", "neu noi quy khong co".

Khong goi external khi:

- Cau hoi da duoc tra loi bang internal policy.
- User dang cap nhat fact.
- User dang yeu cau tao bien ban/preview phieu/gui legal.
- Cau hoi can du lieu noi bo rieng tu ma external khong the biet.

## 5. De xuat: Source Planner va Tool Registry

Them mot tang `Source Planner` truoc retrieval/synthesis.

```json
{
  "source_strategy": "internal_only | internal_then_external | external_not_allowed",
  "external_allowed": true,
  "external_reason": "Internal retrieval did not find enough evidence for litigation handling.",
  "must_disclaim_external": true,
  "high_risk": true,
  "requires_legal_review": true
}
```

### Tool Registry

Khong nen goi MCP rai rac trong node. Nen co registry quan ly tool:

```python
class ResearchTool:
    name: str
    source_type: str
    allowed_intents: list[str]
    max_calls: int
    timeout_seconds: int
    requires_citation: bool
```

Source type nen phan hang:

- `internal_policy`
- `official_law`
- `official_guidance`
- `case_law_or_precedent`
- `trusted_database`
- `general_web`

Voi linh vuc HR/legal, `general_web` chi nen la tham khao thap, khong lam can cu chinh.

## 6. Bat buoc note ro khi dung external

Neu cau tra loi co dung external research, chatbot phai note ro cho user. Vi du:

```text
Luu y: Phan tra loi duoi day dua tren nguon research ben ngoai, khong phai du lieu noi bo cua cong ty. Thong tin nay co the khong chac chan 100% hoac co the thay doi theo thoi diem. Can HR/phap che xac minh truoc khi ap dung vao ho so cu the.
```

Answer payload nen co metadata:

```json
{
  "answer_source": "internal | mixed | external_research",
  "confidence": "high | medium | low",
  "external_disclaimer_required": true,
  "requires_legal_review": true,
  "sources": []
}
```

Quy tac hien thi:

- `internal`: khong can external disclaimer.
- `mixed`: ghi ro phan nao la internal, phan nao la external.
- `external_research`: bat buoc disclaimer o dau cau tra loi.
- Neu khong co citation dang tin cay: khong tra loi nhu ket luan, chi noi chua du can cu.

## 7. Guardrail cho legal/high-risk cases

Auto gan `requires_legal_review=true` neu gap:

- Kien tung/tranh chap lao dong.
- Sa thai/cham dut hop dong.
- Boi thuong thiet hai.
- Cong doan/dai dien nguoi lao dong.
- Lao dong nu mang thai, nuoi con nho.
- Tai nan lao dong, an toan ve sinh lao dong.
- Quay roi, phan biet doi xu.
- Du lieu ca nhan, tiet lo thong tin.
- To cao/khieu nai noi bo.

Voi cac case nay, agent chi nen:

- Tom tat tinh tiet.
- Liet ke fact con thieu.
- Truy xuat can cu co citation.
- Neu dung external thi note ro tinh tham khao.
- De xuat chuyen phap che/nguoi co tham quyen review.

Agent khong nen:

- Chot muc ky luat cuoi cung.
- Ket luan nguoi lao dong co loi neu fact chua du.
- Huong dan bypass quy trinh.
- Dua khuyen nghi phap ly nhu y kien luat su.

## 8. Audit va observability

Can log du de debug va review:

- Fact schema planner version/model.
- Vi sao mot fact duoc hoi.
- Fact nao user sua/xac nhan.
- Source strategy: internal only hay co external.
- Vi sao external duoc goi.
- Tool call input/output summary.
- Source URL/document id.
- `fetched_at`.
- `effective_date` neu co.
- Citation duoc dung trong answer.
- Disclaimer co duoc bat hay khong.
- High-risk flag va legal review flag.

Bang `tool_calls` hien co co the mo rong metadata de ghi cac truong tren.

## 9. Edge case can cover

- User noi "khong biet" cho fact bat buoc.
- User sua fact da confirm.
- User dua nhieu vu viec trong mot message.
- User hoi vua la cau hoi policy vua la yeu cau workflow.
- Internal policy va external law co ve mau thuan.
- Internal data cu/het hieu luc.
- External source khong co ngay hieu luc.
- External search tra ve blog/nguon kem tin cay.
- Prompt injection trong noi dung web/document.
- User yeu cau approve/sign/close/delete/bypass.
- User hoi ve case co yeu to high-risk.
- Incident date trong qua khu, nhung external source la van ban moi.
- Khong co citation du chat luong.

## 10. Roadmap implement de xuat

### Phase 1 - Dynamic fact schema

- Them model/schema cho `FactRequirement`.
- Bien catalog hien tai thanh default templates.
- Them `FactSchemaPlanner`.
- Them validator cho schema do AI de xuat.
- Cho UI/API tra ve required facts dong.
- Giu fallback ve catalog cu neu planner loi.

### Phase 2 - Source planner

- Them `SourceStrategy`.
- Internal retrieval van chay truoc.
- Neu internal rong/yeu va intent phu hop, danh dau can external.
- Chua can goi external that ngay; co the tra message "can external research" de test flow.

### Phase 3 - MCP external research

- Them Tool Registry.
- Them external research node/tool.
- Luu `tool_calls` va source metadata.
- Them source ranking/filter.
- Bat buoc citation va disclaimer.

### Phase 4 - Synthesis va UI

- Hien ro answer source: internal/mixed/external.
- Hien disclaimer khi co external.
- Hien legal review flag.
- Tach citation internal va external.

### Phase 5 - Evaluation

Tao eval set gom it nhat:

- Nghi khong phep.
- Di muon.
- Quay roi.
- Gian lan.
- Xung dot loi ich.
- Tiet lo du lieu.
- Tranh chap luong.
- Tai nan lao dong.
- Don phuong cham dut hop dong.
- Kien tung/tranh chap.

Moi case can check:

- Fact schema co dung khong.
- Cau hoi bo sung co du khong.
- Co goi external dung dieu kien khong.
- Co disclaimer khi dung external khong.
- Co citation khong.
- Co gan legal review cho high-risk khong.

## 11. Ket luan

Huong cai thien nen la:

- Tu hardcoded catalog sang dynamic fact schema co validator va human confirmation.
- Tu internal-only retrieval sang internal-first retrieval, external MCP chi la fallback/bo sung.
- Tu answer mot khoi sang answer co source metadata, citation, disclaimer va legal review flag.

External MCP khong nen la "decision authority". No chi la research assistant khi noi bo khong du thong tin. Moi cau tra loi dua tren external research phai noi ro tinh tham khao, khong chac chan 100%, va can HR/phap che xac minh truoc khi ap dung.
