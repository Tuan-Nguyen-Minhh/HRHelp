# Nghiên cứu giao diện lịch sử trong chat nổi

Ngày nghiên cứu: 17/10/2026. Phạm vi: thanh chọn hội thoại trong khung chat nổi rộng tối đa 420px; không thay đổi luồng xử lý chat.

## Quan sát trước khi chỉnh sửa

- `frontend/src/features/conversation/StandaloneChatPanel.tsx` dùng `<select>` hiển thị tiêu đề hội thoại và một nút chỉ có biểu tượng `+`. Tiêu đề thường là câu người dùng gửi đầu tiên, ví dụ “hello”.
- `frontend/src/index.css` áp `outline: 2px`, `outline-offset: 2px` và `border-radius: 2px` lên mọi phần tử đang có keyboard focus. Quy tắc bo góc này làm hình focus không khớp phần tử có `rounded-lg` trong ảnh.
- `frontend/src/features/conversation/FloatingChat.tsx` giới hạn chiều rộng ở 420px. Thanh lịch sử cần gọn và không làm mất nhiều không gian đọc hội thoại.

## Kết quả từ nguồn sơ cấp

1. Disclosure là một nút mở/đóng nội dung. Nút hỗ trợ Enter/Space, khai báo `aria-expanded` và có thể dùng `aria-controls`. Đây là nền tảng phù hợp để mở danh sách hội thoại đơn giản. [WAI APG — Disclosure](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/).
2. Menu button có hợp đồng khác: Enter/Space mở menu và chuyển focus vào mục đầu tiên; container dùng `role="menu"` cùng các hành vi keyboard của menu. Không nên thêm role này chỉ để có giao diện thả xuống. [WAI APG — Menu Button](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/).
3. Ví dụ disclosure navigation của WAI giữ Tab/Shift+Tab thông thường; Escape đóng danh sách và đưa focus về nút mở. Arrow/Home/End chỉ là bổ sung tùy chọn. Ví dụ cũng giải thích việc tránh role menu khi không triển khai đầy đủ tương tác của menu. [WAI APG — Disclosure Navigation](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/examples/disclosure-navigation/).
4. Nút cần có tên truy cập; nội dung chữ bên trong nút có thể làm tên mặc định. [WAI APG — Button](https://www.w3.org/WAI/ARIA/apg/patterns/button/).
5. `aria-current="true"` mô tả mục hiện tại trong tập các mục liên quan; chỉ đánh dấu một mục hiện tại. Không dùng nó thay `aria-selected` trong widget có semantics lựa chọn riêng. [WAI-ARIA 1.2 — aria-current](https://www.w3.org/TR/wai-aria-1.2/#aria-current).
6. Điều khiển bàn phím cần focus nhìn thấy được; không xóa focus mà không có cách thể hiện thay thế. [WCAG 2.2 — Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html).
7. Mục tiêu trỏ chuột tối thiểu 24×24 CSS px hoặc thỏa ngoại lệ khoảng cách; mục tiêu lớn hơn giúp thao tác dễ hơn. [WCAG 2.2 — Target Size Minimum](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

## Đề xuất thiết kế cho ứng dụng

Các lựa chọn dưới đây là suy luận thiết kế từ không gian thực tế và nguồn trên, không phải kích thước/bố cục W3C bắt buộc:

- Thay ô select bằng nút disclosure dạng thẻ bo góc: biểu tượng lịch sử, nhãn nhỏ “Cuộc trò chuyện”, tiêu đề hiện tại ở dòng chính và chevron. Nút riêng có chữ “Chat mới” đi kèm dấu cộng; tên truy cập có thể dùng “Cuộc trò chuyện mới”. Đây là lựa chọn bố cục cho ứng dụng này, không có nguồn nào ở trên cấm dùng native select để chọn hội thoại.
- Khi mở, hiển thị danh sách các nút hội thoại thường trong một panel có nhãn “Lịch sử trò chuyện”. Không dùng `role="menu"`, `role="listbox"` hoặc `aria-haspopup` nếu chỉ triển khai disclosure.
- Mỗi hàng có biểu tượng chat, tiêu đề, thời điểm cập nhật nếu dữ liệu sẵn có và dấu check cho hội thoại hiện tại; áp `aria-current="true"` lên đúng nút hiện tại. Dùng nền giấy đậm hơn và dấu check để biểu thị mục hiện tại; dành màu đỏ nhạt cho nút tạo chat mới theo bộ màu hiện có.
- Tiêu đề trong thanh đóng dùng một dòng ellipsis; danh sách có thể dùng hai dòng để đọc rõ hơn. Giữ nguyên toàn bộ text trong DOM để tên truy cập không bị cắt. Chặn overflow ngang bằng `min-width: 0`/wrap cho chuỗi dài.
- Danh sách có chiều cao giới hạn và cuộn riêng; mở nó đè lên vùng tin nhắn thay vì kéo dài header. Bảo đảm panel nằm trong khung chat và không bị clipping ở kích thước điện thoại.
- Tab đi qua nút mở, nút chat mới, các nút hội thoại khi danh sách mở và composer theo thứ tự DOM. Escape chỉ đóng danh sách, khôi phục focus về nút mở, và không đồng thời đóng khung chat cha. Sau khi chọn mục, đóng panel và trả focus về nút mở. Đóng khi click ngoài hoặc focus rời nhóm, không giành focus lại từ phần tử người dùng vừa chọn bên ngoài.
- Dùng chiều cao nút 44px và khoảng cách 8px. Giữ focus viền `son` 2px, offset 2px rõ ràng, bo góc khớp nút; tránh vừa outline vuông vừa ring chồng lên nhau. Phạm vi sửa CSS nên ở thanh lịch sử thay vì bỏ focus toàn cục. Màu, typography, đường viền và touch target tuân theo [Design System MASTER](../design-system/hr-help/MASTER.md), nhất là các mục 2, 5 và 7; không thêm hue mới hoặc hex hardcode.
- Có empty/loading/error states ngắn gọn; khóa đổi hội thoại/tạo mới trong lúc gửi như hành vi hiện tại. Không thêm dependency cho disclosure đơn giản này.

## Kiểm tra nghiệm thu

- Desktop 420px và mobile khoảng 360px: tiêu đề dài/chuỗi liền không tràn, nút tạo mới không co mất chữ; danh sách dài cuộn độc lập.
- Dùng Tab, Enter, Space, Escape: mở/chọn/đóng được; focus vẫn nhìn thấy; Escape trong lịch sử không thu nhỏ toàn bộ chat.
- Chọn lịch sử/tạo mới không thay đổi API hoặc cách lưu hội thoại; trạng thái đang gửi vẫn khóa thao tác tương ứng.

## Kết quả triển khai và kiểm tra

Đã áp dụng disclosure trong `ConversationHistory.tsx`, nối vào chat nổi hiện có. Phần này không thêm dependency và không sửa API/backend. Nút tạo mới dùng chữ “Chat mới” làm tên truy cập; nút mở lịch sử giữ cả nhãn nhìn thấy và tiêu đề trong tên truy cập.

`npm run build` thành công. Kiểm tra trình duyệt bằng API mô phỏng với 25 hội thoại đã qua: chọn lịch sử/tạo mới, tiêu đề dài, danh sách cuộn riêng, focus bo góc 12px với outline 2px/offset 2px, Tab/Enter/Space/Escape, click ngoài và kích thước 390px/320px. Escape đóng danh sách trước khung chat, trả focus về nút mở; không có lỗi JavaScript trong các luồng này. Đây là kiểm tra UI, không phải kiểm thử chất lượng trả lời của model.
