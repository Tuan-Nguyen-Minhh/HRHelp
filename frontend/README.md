# Trợ lý chính sách nhân sự

Frontend React cho luồng hồ sơ kỷ luật. Màn hình gọi API hiện có và chỉ hiển thị những gì backend đã lưu.

## Chạy

1. API ở `http://127.0.0.1:8000` (`make run` từ thư mục gốc).
2. Trong thư mục này: `npm install` rồi `npm run dev`.
3. Mở `http://localhost:5173`.

Ở chế độ dev, Vite chuyển `/api` sang cổng 8000. Bản build dùng `http://localhost:8000`, trừ khi đặt `VITE_API_BASE`.

`VITE_AGENT_EVENTS_URL` là địa chỉ SSE tùy chọn. API hiện không phát sự kiện agent, nên thanh trạng thái cập nhật theo từng request.

## Những gì màn hình làm

- Bấm **hình trợ lý nổi ở góc phải dưới** để mở chat ngay trên trang đang xem, không cần tạo hồ sơ. Khung chat giữ nội dung khi thu nhỏ hoặc chuyển trang, có lịch sử hội thoại riêng, hỏi quy định nội bộ, tra cứu nguồn công khai và trò chuyện. Tra cứu quy định tự dùng ngày hiện tại tại Việt Nam.
- Đăng nhập, đăng ký, tạo hồ sơ, hội thoại, đọc tình tiết và báo cáo.
- Khung đăng nhập có bốn tài khoản demo (quản trị viên, quản lý, HR, pháp chế). Chọn vai trò để điền sẵn email/mật khẩu rồi bấm Đăng nhập. Các tài khoản dùng mật khẩu demo từ `scripts/seed_demo_users.py`; chạy script này sau migration nếu cơ sở dữ liệu chưa có tài khoản demo.
- Đẩy phiếu khi `ticket.disposition` là `PREVIEW`.
- Tách luật, nghị định hướng dẫn, nội quy, tiền lệ và xử phạt hành chính theo lớp của báo cáo.
- Không chốt mức kỷ luật, không xếp mức, không tự tính bước đi của hồ sơ ngoài `case.status` và `ticket.disposition`.

Chat độc lập lưu hội thoại qua `/api/v1/conversations`; chỉ chủ sở hữu được đọc và tiếp tục chat. Backend dùng chung bộ định tuyến và các nhánh trả lời của chat hồ sơ, nhưng không đưa các node Planner/Extract Fact và tạo biên bản vào graph. Yêu cầu lập biên bản hoặc thao tác phiếu được hướng sang hồ sơ.
