# HR Help — Design System MASTER

> Global Source of Truth. Mọi trang trong `frontend/` tuân theo file này.
> Trang landing pitch (`LoginPage`) là bản triển khai tham chiếu.
> Page-specific overrides (nếu có) nằm ở `design-system/hr-help/pages/<page>.md` và thắng MASTER.

## 1. Triết lý

**Công cụ pháp lý, không phải trình diễn sản phẩm.** UI gửi tín hiệu trang trọng,
bất biến, truy vết được. Màu là tín hiệu chức năng (đỏ son = cần hành động),
không phải trang trí.

## 2. Màu sắc — hệ Vải lanh + Đỏ son

| Vai trò              | Hex       | Dùng cho                              | Tương phản trên nền chuẩn |
|----------------------|-----------|---------------------------------------|---------------------------|
| `paper` (nền trang)  | `#FBFAF7` | Nền app, nền card                     | —                         |
| `paper-2`            | `#F4F1EA` | Nền phụ, thead, hover hàng            | —                         |
| `paper-3`            | `#EFEBE1` | Viền chip neutral, nền sâu            | —                         |
| `linen` (sidebar)    | `#DCD8CC` | Nền sidebar sáng                      | chữ `#33301F` 9.5:1 AAA   |
| `linen-2`            | `#E7E3D9` | Nền panel phụ                         | —                         |
| `linen-3`            | `#CFCABB` | Nền thanh tiến độ, viền mờ            | —                         |
| `ink` (chữ chính)    | `#332C22` | Tiêu đề, chữ chính trên giấy         | 13.20:1 AAA               |
| `ink-2`              | `#5C554A` | Chữ phụ                               | 7.05:1 AAA                |
| `ink-3`              | `#756F63` | Chữ mờ (label, hint)                  | 4.78:1 AA (trên giấy) |
| `ink-4`              | `#A29B8D` | Placeholder, disabled — KHÔNG dùng làm text | —                    |
| `rule` (viền)        | `#D8D1C3` | Viền card, input                      | —                         |
| `rule-2`             | `#B8AE9C` | Viền đậm, focus ring phụ              | —                         |
| `son` (đỏ son)       | `#8C2B2B` | CTA chính, badge hành động, con dấu, link nhấn | trắng trên son 8.42:1 AAA |
| `son-dark`           | `#722222` | Hover CTA                              | —                         |
| `son-tint`           | `#F6EAE7` | Nền cảnh báo nhẹ                      | chữ son trên tint 7.15:1  |
| `son-line`           | `#E2C4C0` | Viền cảnh báo                          | —                         |
| `solid` (nâu da)     | `#4A3F30` | Nút phụ đậm, ô đã xong, section 4 lớp cũ | giấy trên solid 9.84:1 AAA |

### Quy tắc dùng màu

1. Đỏ son CHỈ cho: CTA chính, trạng thái cần hành động, con dấu, link quan trọng.
2. Trạng thái còn lại phân bằng **độ đậm của mực**, không thêm hue mới.
3. KHÔNG dùng xanh lá/xanh dương/vàng làm màu phân loại (toàn trang chỉ có 1 hue).
4. CẤM Tailwind default palette (`slate-*`, `neutral-*`, `brand-*/cyan`) và hex hardcode
   ngoài bảng trên. Mọi màu đi qua token `linen/ink/son/rule`.

## 3. Typography

| Vai trò | Font | Ghi chú |
|---------|------|---------|
| UI + chrome | **Public Sans** 400/500/600/700 | Mọi control, bảng, nav, chat |
| Văn bản pháp lý | **Literata** 400/600 (+italic) | CHỈ trong khối biên bản/quyết định/trích dẫn dài |
| Số liệu | Public Sans, `tabular-nums` | Không dùng font khác cho số |

Cả hai font đều có subset `vietnamese` (đã kiểm chứng qua Google Fonts CSS).
Tiêu đề hero dùng `text-wrap: balance`. Không serif ở bảng, nav, badge.

## 4. Mật độ (data-dense, theo skill ui-ux-pro-max)

```
--grid-gap: 8–16px · --card-padding: 12–16px · --table-row-height: 36–42px
--sidebar-width: 240–256px · --header-height: 56–60px
font-size: 12–14px cho bảng · sticky table headers · bảng cuộn ngang có min-width
```

## 5. Component

- **Card**: `rounded-xl`, nền `#FFFFFF` trên nền trang giấy, viền `rule`.
  Khối lồng nhau dùng `paper-2`. Card tương tác mới có hover;
  card chỉ đọc KHÔNG hover (tránh tín hiệu "bấm được" sai).
  Không box-shadow trừ khi cần (theo Minimalism & Swiss).
- **Button**: primary = `son` nền chữ trắng; secondary = viền `rule-2`;
  cao tối thiểu 36–40px; `cursor-pointer` ở mọi phần tử bấm được.
- **Badge/chip**: thang mực (solid → neutral → faint) + `son` cho cần hành động.
  KHÔNG in mã trạng thái tiếng Anh raw ra UI.
- **Input/select/textarea**: viền `rule`, focus ring `son` 2px + offset 2px.
- **Ô trống trong văn bản**: gạch chân chấm đỏ (`border-bottom: 1px dotted son`),
  không dùng chip vàng.
- **Table**: thead `paper-2`, chữ thead uppercase 10–10.5px `ink-3`,
  hover hàng `paper-2`, mã điều luật in đậm.

## 6. Motion (2 tầng)

| Tầng | Dùng ở đâu | Quy tắc |
|------|-----------|---------|
| **Full** | Landing pitch (`/login`) | GSAP: reveal 620–900ms `power2.out`, stagger ≤0.1; chat loop; 4-layer + impact auto-cycle 2.2s; parallax chỉ lớp trang trí; magnetic đúng 1 nút CTA |
| **Subtle** | Toàn bộ app đã login | Fade chuyển trang 250ms, hover row/card 200ms, skeleton shimmer 1400ms; KHÔNG auto-play, KHÔNG scrub-pin |

Chính sách: **mặc định full cho mọi visitor** (`localStorage hrhelp:motion`;
`lite` = tắt). Không đọc `prefers-reduced-motion` của OS làm mặc định vì
Windows tắt hiệu ứng vì pin/hiệu năng, không phải vì nhạy cảm chuyển động.
Công tắc thủ công nằm ở nav landing.

## 7. Accessibility (bắt buộc mỗi phase)

- Text ≥4.5:1, non-text ≥3:1 (bảng §2 đã đo).
- Focus ring `son` 2px + offset 2px cho MỌI `a/button/select/input/textarea/[tabindex]`.
- Loading: skeleton + `aria-busy`, không `<p>Đang tải…</p>` trơ.
- Touch target ≥44px (iOS) / 48dp (Android).
- `prefers-reduced-motion`: vẫn phải render trạng thái cuối đầy đủ.
- Không emoji làm icon (lucide-react), không icon-font (đã gỡ Font Awesome).
- Marquee/carousel (nếu có) phải có nút pause + dừng khi focus.
