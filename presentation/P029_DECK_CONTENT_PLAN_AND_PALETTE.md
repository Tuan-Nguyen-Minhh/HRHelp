# P-029 · HR Help — KẾ HOẠCH DECK v2 (tasteskill-compliant)

> **Mục tiêu:** nhấn mạnh (1) **NỖI ĐAU** kỷ luật lao động và (2) **GIẢI PHÁP KIẾN TRÚC** (Multi-Agent + Hybrid GraphRAG + HITL).
> **Phương pháp:** skill `design-taste-frontend` (tasteskill / anti-slop) làm *luật*, skill `design-system` (Slide System) làm *cấu trúc slide*.
> **Nguồn màu (bất biến):** `design-system/hr-help/MASTER.md` — hệ "Vải lanh + Đỏ son".
> **Nguồn số liệu:** `eval/case_assessment/results/live_retrieval_mistral8b/summary.json`.
> **Lưu ý áp dụng:** tasteskill viết cho *web page*. Mình map sang *slide 16:9* — chỗ nào chỉ có nghĩa trên web sẽ ghi rõ "(web-only)".

---

## 0 · VÌ SAO BẢN NÀY KHÁC BẢN CŨ

| Vấn đề bản cũ | tasteskill nói gì | Bản v2 làm |
|---|---|---|
| Chỉ có 2 ground (sáng/tối) → đơn điệu | Đổi cả field nền giữa các section là "the strongest colour move available"; "several flat colours 13%" | **Colour-by-chapter:** thang sáng 4 bậc (giấy 98 · putty 93 · đá 84 · taupe 74). Không nền tối, không nền đỏ |
| Cảnh báo "cream + warm accent" (họ bị cấm) | "Cream with terracotta" bị fail; oxblood ink **được phép**; warmth không phải beige | Nền giữ **bone chroma thấp (≤15%)**; đỏ son **chỉ còn accent nhỏ**, không bao giờ làm nền |
| "Quá loá" | Accent **<5%/màn**; cấm gradient/glow/neon; "flat colour with conviction" | Field phẳng, cạnh cứng, không fade; accent chỉ cho 1 việc |
| Thiếu ý tưởng chủ thể → dễ slop | "Removal is not enough… the idea comes from the subject" | Ý tưởng: **Con dấu + Hồ sơ giấy** (từ logo landing) |

---

## 1 · RÀNG BUỘC tasteskill (LUẬT BẮT BUỘC)

### 1.1 House rules (đo được)
Headline **≤2 dòng** ở mọi khổ · câu văn lớn đặt ở cỡ *statement* (≤36px desktop), không phải heading · **không eyebrow/kicker** · **không monospace** ngoài code · **không index 01/02/03** · **không hairline rule/lưới kẻ** · **không gradient** · **không bóng ở trạng thái tĩnh** · **không glass/backdrop-blur** · **không "assistant palette" (kem+terracotta, tím/indigo)** · **không caption chữ nhỏ in hoa** · **không 3 card feature y hệt** · **không emoji icon** · tối đa **2 họ font**.

### 1.2 Tells bị cấm (đã gỡ khỏi plan này)
Violet/indigo gradient · gradient text · nút glow · near-black + neon + glow · 3 feature card y hệt có icon ô vuông · emoji · pill badge trên headline · 1 từ trong headline styled khác · monospace micro-label · index numbering · hairline khắp nơi · caption caps nhỏ rải rác · headline dài >2 dòng · mọi thứ căn giữa · social proof bịa · fake dashboard bằng thanh xám.

### 1.3 Điều bản v2 **chủ động thêm** (tránh "avoidance aesthetic")
tasteskill: *"A page with every tell removed and nothing put in their place is an empty page with good manners."*
→ Mỗi slide phải có: **1 chủ thể lớn**, **type set lớn**, **field màu phẳng**, **ảnh UI thật**. Không để slide trống.

---

## 2 · CHIẾN LƯỢC & Ý TƯỞNG

| Thuộc tính | Chọn |
|---|---|
| Strategy | Product Demo × Duarte Sparkline (What Is ↔ What Could Be) |
| Số slide | 10 (+ phụ lục) |
| Emotion arc | curiosity → frustration → fear → relief → interest → confidence → confidence → trust → trust → urgency |
| Pattern break | slide **3** (nỗi đau đỉnh) và **6** (vào kiến trúc) |

**Ý TƯỞNG (bắt buộc, từ chủ thể):**
> Trên deck này, **con dấu đỏ son** trở thành **dấu niêm của mỗi field chương**; **hồ sơ giấy** trở thành **nền field** — mỗi chương như một trang hồ sơ được đóng dấu.

**Signature move:** **Colour by chapter** (ground đổi ở mỗi chương — xem §7).
**"Live thing" (nếu dựng HTML):** QR mở **live demo** HR Help thật / chart RAGAS bấm chạy lại. *(web-deck optional)*

---

## 3 · COLOUR BY CHAPTER — HỆ FIELD (thay "sáng/tối")

> Đây là điểm quan trọng nhất sửa nỗi đau "đơn điệu". **Không** còn hai nền sáng/tối; có **4 field phẳng** xếp như chương, mỗi field có ink riêng, **gặp nhau edge-to-edge, cạnh cứng, không fade**.

### 3.1 Field (ground phẳng) — thang sáng rộng (chốt V2a)

| Field | Ground | Vai trò chương | Độ sáng |
|---|---|---|---|
| **P · Giấy** | `#FBFAF7` (paper) | Cover, chương kiến trúc, đóng (bookend) | 98 |
| **U · Putty** | `#F0EBE0` `[DER]` | Chương nhẹ: giải pháp, quản trị | 93 |
| **S · Đá** | `#DCD8CC` (linen) | Chương đọc chính: nỗi đau, demo, minh chứng | 84 |
| **T · Taupe** | `#C4B9A3` `[DER]` | Chương "nặng": cái giá và đào sâu kỹ thuật | 74 |

- **Không còn nền tối, không còn nền đỏ chói.** Ink duy nhất: `#332C22`. Không có field nào khác hue.
- **Bước nhảy tối thiểu ≥ 9 điểm sáng** giữa hai field liền kề. Tuyệt đối không để P (98) cạnh U (93) vì chỉ lệch 5.
- Accent `son #8C2B2B` chỉ là **dấu nhỏ** (chấm, thanh 4px, gạch chân), **không bao giờ làm nền**.
- Trên nền Taupe, accent chữ phải dùng `son-dark #722222` (5.5:1), vì `son` chỉ đạt 4.3:1.
- `#F0EBE0` và `#C4B9A3` là `[DER]` cùng hue linen, chỉ đổi lightness.

### 3.2 Tỉ lệ & luật accent
- **Ground 70–90%** mỗi màn · **accent <5%/màn** (đánh dấu đúng 1 việc, cùng lắm 1 thứ lặp lại).
- **Accent KHÔNG dùng cho heading** — headline là ink. Accent không rải cho icon/bullet/viền.
- Field gặp nhau **cạnh cứng** — không gradient, không đổ bóng, không bo mờ chuyển nền.

### 3.3 Tương phản (đo)
| Cặp | Tỉ lệ | |
|---|---|---|
| `ink` trên Giấy `#FBFAF7` | 13.2:1 | AAA |
| `ink` trên Putty `#F0EBE0` | ~12:1 | AAA |
| `ink` trên Đá `#DCD8CC` | 9.3:1 | AAA |
| `ink` trên Taupe `#C4B9A3` | 7.0:1 | AAA |
| `son` trên Giấy / Đá / Putty | ≥5.6:1 | AA |
| `son-dark` trên Taupe | 5.5:1 | AA |
| trắng trên `son` | 8.42:1 | AAA |

### 3.4 Token (roles + fields)
```css
:root{
  /* hue gốc — từ MASTER.md */
  --paper:#FBFAF7; --linen:#DCD8CC; --linen-2:#E7E3D9; --linen-3:#CFCABB;
  --ink:#332C22; --ink-2:#5C554A; --ink-3:#756F63;
  --solid:#4A3F30; --son:#8C2B2B; --son-dark:#722222; --son-tint:#F6EAE7; --son-line:#E2C4C0;
  /* derived (cùng hue linen, chỉ đổi lightness) */
  --putty:#F0EBE0; --taupe:#C4B9A3;

  /* roles */
  --bg:var(--paper); --text:var(--ink); --muted:var(--ink-2); --accent:var(--son);
  /* fields */
  --field-p:var(--paper); --field-u:var(--putty); --field-s:var(--linen); --field-t:var(--taupe);
}
```

### 3.6 Map slide → field
Nhịp độ sáng: `98 · 84 · 74 · 93 · 84 · 98 · 74 · 93 · 84 · 98`

| Slide | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Field | **P** | **S** | **T** | **U** | **S** | **P** | **T** | **U** | **S** | **P** |

- Slide 3 (nỗi đau) và 7 (đào sâu GraphRAG) đặt trên bậc đậm nhất **Taupe** để tạo trọng lượng.
- Cover và slide đóng cùng ở **Giấy** (bookend), cách nhau bởi 8 chương để không lặp cảm giác.

### 3.5 Dữ liệu & rủi ro (một hue — `[SRC]`)
- **Risk:** LOW `#756F63` · MEDIUM `#4A3F30` · HIGH `#8C2B2B` · CRITICAL `#722222`.
- **Chart RAGAS:** cột cao tô **đặc** `son #8C2B2B`; cột thấp **viền + tint** `#E2C4C0` (trung thực với số thấp).

---

## 4 · TYPE SYSTEM (`type.md`) — "to vừa phải"

Slide dùng **kích thước cố định theo px** (khung 1920×1080), không dùng `vw`:

| Vai trò | 1920×1080 | 1280×720 | Font · weight |
|---|---|---|---|
| Display (tên/statement) | **72px** | 48px | Literata 500 |
| Headline slide | **56px** | 38px | Literata 500 |
| Lead | **30px** | 20px | Public Sans 500 |
| Body / bullet | **24px** | 16px | Public Sans 400 |
| Small (nguồn, nhãn) | **16px** | 13px | Public Sans 400 |
| Số liệu lớn | **96px** | 64px | Public Sans 700, tabular-nums |

- Cố ý chọn **"to vừa phải"**: headline 56px, không phóng tới 120px. (Đây là *lệch có chủ đích* khỏi lời khuyên "pull the scale hard" của tasteskill, theo yêu cầu.)
- Vẫn giữ **1 size dẫn đầu mỗi slide**; thứ tự nhấn: số liệu lớn > display > headline.
- Display/headline: `line-height 1.05`, `letter-spacing -0.02em`, `text-wrap: balance`, `max-width ~18ch`.
- Số luôn `tabular-nums`; tối đa 2 họ font; không all-caps quá 3 từ; không text <15px (ở 1920).
- Font: **Literata** (display) + **Public Sans** (còn lại), cả hai có subset `vietnamese`.

---

## 5 · NỘI DUNG & VĂN PHONG 10 SLIDE (bản chốt)

### 5.0 Quy tắc văn phong (bắt buộc)
- **Ngắn, xúc tích:** mỗi dòng 2 đến 6 từ; mỗi slide tối đa 4 dòng nội dung.
- **Không emoji** ở bất kỳ đâu.
- **Không dash:** không dùng `—`, `–`, `-` trong chữ hiển thị. Khoảng số viết "từ 4 đến 8" thay vì "4-8".
- **Font to vừa phải:** headline 56px, body 24px (khung 1920), xem §4.
- **Nỗi đau là tâm điểm:** slide 2 và 3 dồn lực; câu ngắn, dứt khoát.
- Headline **sentence case**, không dấu chấm cuối.
- Viết giảm dash ở tên kỹ thuật khi được ("đa tác tử" thay "Multi-Agent", "mở rộng đồ thị một bước" thay "1-hop"). Mã đội hiển thị `P029`; mã chính thức trong repo là P-029.

### 5.1 Copy deck (chữ đặt trên slide)

| # | Field | Shape | Headline | Dòng trên slide |
|---|---|---|---|---|
| 1 | P | cover | **HR Help** | `Trợ lý AI cho nghiệp vụ kỷ luật lao động` / `P029` / `VinUni AI20K Build Phase` |
| 2 | S | split | **Một vụ vi phạm, một rừng văn bản** | `Bốn tầng văn bản cho một vụ` · `Điều khoản dẫn chiếu lẫn nhau` · `Tra cứu thủ công tốn hàng giờ` · `Mỗi phòng ban xử một kiểu` |
| 3 | T | stat | **Sai thủ tục, mất cả vụ kiện** | `Thiếu biên bản` · `Sai thời hiệu` · `Thiếu họp công đoàn` · `Sai thẩm quyền ký` → `Bồi thường, buộc nhận lại lao động, phạt hành chính` |
| 4 | U | flow | **Từ mô tả thô đến hồ sơ kỷ luật** | `Làm rõ tình tiết` · `Tra cứu theo hiệu lực` · `Đánh giá rủi ro` · `Soạn bản nháp` · `Con người quyết định` |
| 5 | S | screenshot | **AI hỏi, người xác nhận** | `Hỏi để đủ căn cứ` · `Khóa dữ kiện` · `Trích dẫn nguồn` · `Xuất hồ sơ Word` |
| 6 | P | diagram | **Ba agent, chốt chặn bằng Python** | `Case Graph` → `CaseHandoff` → `Recommendation` → `Dispatch Gate` · `LLM không chọn bước, Python chọn bước` |
| 7 | T | pipeline | **Đúng điều khoản, đúng thời điểm** | `Dense` · `BM25 hai kho` · `RRF` · `Cohere rerank` · `Mở rộng đồ thị một bước` · `Mười hai đoạn chứng cứ` · `Lọc theo ngày vi phạm` |
| 8 | U | table | **AI phân tích, người quyết định** | `AI làm: hỏi làm rõ, trích dẫn điều khoản, tính rủi ro, soạn nháp` / `Người quyết: Pháp chế duyệt, Người có thẩm quyền ký` |
| 9 | S | chart | **Độ tin cậy, đo bằng số** | `Context Precision 91.41%` · `Faithfulness 82.45%` · `Factual Correctness 57.60%` · `Context Recall 34.96%` / `Đo trên live pipeline, 5 ca thực tế` |
| 10 | P | timeline | **Từ hồ sơ giấy đến HR Help** | `Tích hợp hệ thống HR` → `Mở rộng nghiệp vụ` → `Trợ lý phiên hòa giải` · `Live demo` · `Q&A` |

> Quy tắc shape: **không 2 slide cạnh nhau trùng shape**. Shape lặp 3 lần = template lộ.

### 5.2 Speaker notes (mỗi slide 1 câu)
1. "Kỷ luật lao động là nghiệp vụ dễ mất tiền nhất trong HR. HR Help phân tích và soạn nháp, còn quyền quyết định nằm ở con người."
2. "HR không thiếu kiến thức. Vấn đề là luật phân tán và dẫn chiếu lẫn nhau, nên rất dễ bỏ sót một dòng trình tự."
3. "Đau nhất không phải nhân viên sai, mà là hồ sơ sai. Một cuộc họp công đoàn thiếu là đủ để thua kiện."
4. "Không phải chatbot tra cứu. Đây là một quy trình năm bước, kết thúc bằng chữ ký của con người."
5. "Nhập tình huống, agent hỏi lại cho đủ căn cứ. Xác nhận xong, hệ thống khóa dữ kiện và trả về trích dẫn kèm bản nháp."
6. "Ba agent tách biệt, giao tiếp qua dữ liệu bất biến. Điểm mấu chốt: LLM không chọn bước, Python chọn bước."
7. "Điều khoản luật dẫn chiếu lẫn nhau. Chúng tôi mở rộng đồ thị một bước để luôn lấy đủ chế tài và trình tự, chỉ dùng văn bản còn hiệu lực tại ngày vi phạm."
8. "Trong pháp lý, AI không thể ra quyết định. AI chuẩn bị hồ sơ và cảnh báo, quyền duyệt và ký thuộc về con người."
9. "Đây là số đo, không phải lời hứa. Context Precision 91.41% và Faithfulness 82.45% trên live pipeline với năm ca thực tế."
10. "Cảm ơn hai anh mentor đã định hướng từ Gate G1. HR Help sẽ nằm trong chính hệ thống HR doanh nghiệp đang dùng."

### 5.3 Phụ lục (nếu hỏi sâu)
A1 HOLD/SUBMIT · A2 state machine hồ sơ · A3 `document_chunks` vs `legal_*` + 599 refs · A4 giới hạn (corpus demo-grade, reference chưa expert-review).

---

## 6 · IMAGERY (`imagery.md`)

- **Tối thiểu 4 ảnh THẬT** (ảnh UI sản phẩm tính là real): slide 1 (UI + con dấu), slide 5 (3–4 screenshot), + tùy chọn 1 ảnh tư liệu luật từ **open collection** (Wikimedia/Met…) có credit — dùng ở slide 2/3 như "thế giới của chủ thể".
- **1 ảnh động:** clip demo HR Help (muted loop) hoặc drift chậm trên screenshot hero.
- **Cấm:** dashboard giả bằng thanh xám, ảnh stock người/office chung chung, box xám thay ảnh, ảnh nghiêng tỉ lệ.
- Crop cùng tỉ lệ; KHÔNG viền ảnh — nếu ảnh chìm vào nền thì đổi crop hoặc đặt trên `--surface`.

---

## 7 · MOTION (`motion.md`)

- **Signature move: Colour by chapter** — ground đổi ở biên chương theo nhịp sáng `P(98) → S(84) → T(74) → U(93) → S(84) → P(98) → T(74) → U(93) → S(84) → P(98)`; cạnh cứng, tuyệt đối không fade.
- **Entrance** cho các slide "reveal" (2,4,5,6,7,8,9): heading → nội dung → hình, stagger **60–90ms**, rise 16–32px + opacity, **một lần**.
- **Feedback:** nếu HTML — điều hướng phím/mũi tên + progress bar; không hover lift mọi card.
- **Tokens:** `--ease-out cubic-bezier(.22,1,.36,1)`, `--t-reveal 800ms`, press 140ms, hover 180ms.
- **Cấm:** cùng một fade-up cho mọi slide · bounce/elastic · reveal không fallback · animate layout props. Chỉ `transform/opacity/clip-path`.

---

## 8 · COPY RULES (`copy.md`)

- Headline **≤2 dòng**, ~**≤32 ký tự** (đã canh ở §5), **sentence case**, không dấu chấm cuối.
- **Cấm** động/tính từ genre: unlock, supercharge, seamless, elevate, cutting-edge… · "not just X, it's Y" · tricolon "Fast. Simple. Secure." · nhãn giả editorial ("Field notes"…) · em dash như thói quen · nhãn bước trùng số ("Step 1").
- **Proof:** không bịa khách hàng/quote/logo/benchmark. Dùng: ảnh UI thật · cách hoạt động cụ thể · số liệu thật từ eval.
- Micro-typography: nháy cong “ ” ’, en dash –, `tabular-nums` ở bảng/số, `text-wrap: balance` (heading) / `pretty` (đoạn), non-breaking space số+đơn vị.

---

## 9 · CRITIQUE & SCORING GATE (`critique.md`)

Chấm như juror Awwwards: `overall = 0.4·design + 0.3·usability + 0.2·creativity + 0.1·content`.
**Caps:** còn FAIL → ≤6.0 · headline ≥3 dòng / eyebrow / mono label / index 01-02 / gradient / bóng tĩnh / hairline → ≤6.5 · pass 3 fail (deck dùng được cho ai cũng được) → creativity ≤6 · <4 ảnh thật → design ≤6.5 · gần như không động → design ≤7 · placeholder → content ≤5.
Quy trình: **tối đa 3 vòng** critique → sửa top-3 → inspect lại. Nếu vòng 3 <7.5 thì nói thẳng, không làm tròn.
*(Nếu dựng HTML: chạy `scripts/lint.mjs` + `scripts/inspect.mjs` — cần Node 22 + Chrome.)*

---

## 10 · CHECKLIST CHỐNG AI-SLOP (duyệt trước khi chốt)

- [ ] Không có tell nào ở §1.2 xuất hiện trên slide.
- [ ] Mỗi slide có **1 chủ thể lớn** + field phẳng; không slide nào trống/rỗng.
- [ ] Headline ≤2 dòng, ≤~32 ký tự; không orphan 1 từ.
- [ ] ≥4 ảnh thật + 1 ảnh động; không dashboard giả/box xám.
- [ ] Accent son <5%/màn; headline là **ink**, không phải accent.
- [ ] Field kề nhau lệch **≥9 điểm sáng**; cạnh cứng, không gradient/fade.
- [ ] Không 2 slide cạnh nhau trùng shape.
- [ ] Không field nào là nền tối hay nền đỏ; đỏ son chỉ dạng dấu nhỏ; trên Taupe dùng `son-dark`.
- [ ] Số liệu RAGAS khớp `summary.json`; con số ngoài có nguồn hoặc định tính.
- [ ] Font Literata + Public Sans (subset `vietnamese`); tối đa 2 họ.

---

## 11 · HANDOFF — việc phải làm trước khi chốt

| # | Việc | Ở đâu | Ai |
|---|---|---|---|
| 1 | Thay mock chat bằng **3 ảnh UI thật** (chat làm rõ · fact đã khóa · báo cáo trích dẫn). Crop cùng tỉ lệ, gợi ý 16:10, rộng ≥1600px | `p029-deck.html`, slide 5, khối `.mock` (có comment đánh dấu) | member |
| 2 | Chụp thêm 1 ảnh case workspace cho slide 1 (tùy chọn) | slide 1 | member |
| 3 | Xác minh 2 con số/nguồn nếu muốn đưa vào slide 3 (hiện đang dùng câu định tính để không bịa) | slide 3 | team |
| 4 | Ghi rõ reference eval còn `draft_pending_expert_review` khi trình bày | slide 9 | team |

**Trạng thái artifact:**
- `p029-deck.html` — deck **13 slide**, đã áp V2a, có sơ đồ kiến trúc + pipeline, thêm slide Tính khả thi và Thách thức.
- `p029-deck.pptx` — bản PPTX 16:9 (13 slide, mỗi slide là ảnh full-bleed render từ HTML). **Không sửa chữ trực tiếp trong PowerPoint được** — muốn sửa thì sửa `p029-deck.html` rồi render lại.
- `P029_DECK_CONTENT_PLAN_AND_PALETTE.md` — spec (palette + văn phong + checklist).
- `template-light-variants.html` — bản so V2a/V2b (đã chốt V2a).
- `template-colors-variants.html` — bản so 3 phương án nền (đã loại).
- `template-slide-colors.html` — bản cũ dùng nền đen + đỏ (đã loại, giữ làm mốc).

---

## 12 · ĐỐI CHIẾU TIÊU CHÍ BTC (§9.6) & CẬP NHẬT DECK LÊN 12 SLIDE

Deck `p029-deck.html` đã mở rộng lên **12 slide** (từ 10) để phủ đủ 4 phần: **bài toán · giải pháp · tính khả thi · định hướng phát triển**.

| # | Slide | Field | Phủ tiêu chí BTC §9.6 |
|---|---|---|---|
| 1 | HR Help (cover) | P | 1 Title |
| 2 | Một vụ vi phạm, một rừng văn bản | S | 2 Problem |
| 3 | Sai thủ tục, mất cả vụ kiện | T | 2 Problem (agitation) |
| 4 | Từ mô tả thô đến hồ sơ kỷ luật | U | 3 Solution |
| 5 | AI hỏi, người xác nhận | S | 4 Product Demo |
| 6 | Kiến trúc: bốn tầng, một chốt chặn | P | 5 Architecture (**sơ đồ hộp + mũi tên luồng dữ liệu**) |
| 7 | Đúng điều khoản, đúng thời điểm | T | 6 AI/LLM approach (**sơ đồ pipeline 4 chặng**) |
| 8 | **Trích đúng điều, đúng khoản** | S | 6 (trích dẫn **chữ thật** từ corpus dự án) |
| 9 | AI phân tích, người quyết định | U | 6 governance / HITL |
| 10 | **Tính khả thi** | S | **7 Technical Highlights** |
| 11 | Độ tin cậy, đo bằng số | P | 6 Evaluation metrics |
| 12 | **Ba điểm nghẽn và cách vượt** | T | **9 Challenges & Learnings** |
| 13 | Từ hồ sơ giấy đến HR Help | P | 10 Team + Next Steps (**dải đội ngũ**) |

**Đã xong:**
- **Ảnh UI thật** (chạy app local, đăng nhập `hr.demo`, tạo hồ sơ `KN-2026-002` rồi đi qua luồng thật):
  - slide 1: `assets/landing.png` (cover)
  - slide 5: `assets/chat-clarify.png` — ảnh gốc **nguyên khung** (có sidebar, header), **1 ảnh duy nhất**; đã rollback bản cắt Python
  - dự phòng: `assets/chat-zoom.png` (bản cắt sát, chữ to hơn), `assets/evidence.png`, `assets/dashboard.png`
- **Slide 6 kiến trúc = sơ đồ hộp + mũi tên** (Vite React → FastAPI → LangGraph → PostgreSQL, nhánh xuống Dịch vụ AI ngoài), không còn dải tầng chữ.
- **Slide 8 dùng chữ thật, KHÔNG dùng ảnh chụp**: nguồn `eval/case_assessment/ragas_dataset.json` — BLLĐ 2019 Điều 125 khoản 4; Nội quy Điều 4 khoản 3; Nội quy Điều 15 khoản 1.
- **Live URL** `c4-app-029.vercel.app` đã ghi vào slide 10 (Tính khả thi) và slide 13.

**Bài học ảnh chụp:** ảnh UI để nguyên cả màn hình rồi thu nhỏ sẽ không đọc được. Bắt buộc **cắt sát vùng quan trọng rồi phóng to** (mỗi slide 1 ảnh).

**Còn thiếu trước khi chốt:**
1. **Demo video (QR)** — chưa có; cần link YouTube + QR cho slide 12.
2. **Số liệu có nguồn** cho slide 2/3 (đang dùng câu định tính để không bịa).
3. **Tên + vai trò thành viên** ở slide 12 (đang `[Tên]`).
4. **Cost/latency** mỗi hồ sơ — chưa đo.
5. **CI** đang `on: workflow_dispatch` — nên bật `on: push` cho đúng tinh thần CI/CD của BTC.

**Xung đột cần biết:** §9.6 khuyến nghị *dark background + light text* cho máy chiếu và *≤30 từ/slide*. Deck dùng **nền sáng (V2a)** theo lựa chọn của bạn — cần thử trên máy chiếu thật; và nhiều slide vượt 30 từ do thêm sơ đồ/nhãn.
