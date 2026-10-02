# Trợ lý chính sách nhân sự

Frontend React cho luồng hồ sơ kỷ luật. Màn hình gọi API hiện có và chỉ hiển thị những gì backend đã lưu.

## Chạy

1. API ở `http://127.0.0.1:8000` (`make run` từ thư mục gốc).
2. Trong thư mục này: `npm install` rồi `npm run dev`.
3. Mở `http://localhost:5173`.

Ở chế độ dev, Vite chuyển `/api` sang cổng 8000. Bản build dùng `http://localhost:8000`, trừ khi đặt `VITE_API_BASE`.

`VITE_AGENT_EVENTS_URL` là địa chỉ SSE tùy chọn. API hiện không phát sự kiện agent, nên thanh trạng thái cập nhật theo từng request.

## Những gì màn hình làm

- Đăng nhập, đăng ký, tạo hồ sơ, hội thoại, đọc tình tiết và báo cáo.
- Đẩy phiếu khi `ticket.disposition` là `PREVIEW`.
- Tách luật, nghị định hướng dẫn, nội quy, tiền lệ và xử phạt hành chính theo lớp của báo cáo.
- Không chốt mức kỷ luật, không xếp mức, không tự tính bước đi của hồ sơ ngoài `case.status` và `ticket.disposition`.

API chưa có danh sách hồ sơ, lịch sử tin nhắn, hay thao tác duyệt của pháp chế. Hội thoại giữ trong phiên trình duyệt. Khi hồ sơ đã vào hàng chờ, trang pháp chế chỉ đọc hồ sơ và để các nút duyệt ở trạng thái tắt.
