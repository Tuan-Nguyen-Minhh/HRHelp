# Pitch Deck & Demo Materials

## Files

- `p029-deck.html` — nguồn chính của deck (17 slide, 16:9). Sửa nội dung tại đây.
- `p029-deck.pdf` — bản PDF xuất từ HTML, mỗi slide một trang landscape.
- `p029-deck.pptx` — bản PPTX cũ (ảnh full-bleed). Cần render lại sau khi sửa HTML.
- `assets/` — ảnh UI thật dùng trong deck.
- `P029_DECK_CONTENT_PLAN_AND_PALETTE.md` — palette, văn phong, checklist.

## Xuất PDF

PDF được in trực tiếp từ HTML bằng Chrome headless. Ảnh trong `assets/` là ảnh local nên được nhúng vào PDF, không phụ thuộc link ngoài.

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --headless=new --disable-gpu --no-pdf-header-footer `
  --virtual-time-budget=12000 `
  --print-to-pdf="presentation\p029-deck.pdf" `
  "file:///C:/Users/tuan/Desktop/P-029/presentation/p029-deck.html"
```

Hoặc mở `p029-deck.html` trong Chrome, chọn Print, chọn Landscape, Margins None, Background graphics. `@media print` đã khóa mỗi slide vào một trang 13.333 x 7.5 inch.

Lưu ý:

- Không đổi `@page` hoặc bỏ `@media print` nếu muốn PDF 16:9.
- Font Literata/Public Sans tải từ Google Fonts; nếu máy offline, PDF sẽ dùng font fallback.
- PPTX hiện là ảnh render, không sửa chữ trực tiếp được; sửa HTML rồi render lại.
