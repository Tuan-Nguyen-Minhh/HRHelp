# Kế hoạch Logic: Tiền xử lý (Preprocessing) Văn bản Pháp luật

Mục tiêu của bước Preprocessing là chuyển đổi một văn bản trình bày phẳng thành một cấu trúc dữ liệu có phân cấp ngữ nghĩa rõ ràng, xử lý triệt để các edge cases đặc thù của văn bản luật Việt Nam nhằm phục vụ cho hệ thống RAG (AI).

Dưới đây là 5 bước tư duy logic đã được tối ưu hóa độ chính xác:

## 1. Làm sạch sơ bộ (Pre-cleaning)
*   **Logic:** Phải thực hiện triệt để ĐẦU TIÊN để tạo môi trường an toàn cho các tập Regex phía sau hoạt động.
*   **Hành động:** 
    *   Xóa các ký tự escape sai do MarkItDown sinh ra (như `\_`), chuẩn hóa toàn bộ khoảng trắng kép, tabs.
    *   *Quy tắc loại trừ gộp dòng (Line-merge Exclusion):* Khi xử lý ngắt dòng bất thường giữa câu trong đoạn văn thường, **tuyệt đối loại trừ** các dòng là Structural Markers (`Phần`, `Chương`, `Mục`, `Điều`) và các dòng ngay sau chúng. Toàn bộ các dòng này phải được giữ nguyên cấu trúc dòng độc lập để nhường quyền xử lý gộp chuyên biệt cho Bước 4.

## 2. Trích xuất Metadata đa chiều (Metadata Anchoring)
*   **Số hiệu văn bản:** Sử dụng Regex an toàn `^Số:\s*([A-Za-z0-9/_\-]+)` (lưu ý đưa dấu `-` ra cuối class để tránh lỗi ASCII range) nhằm tách chính xác số hiệu.
*   **Loại & Tên văn bản (Tách lớp & Điều kiện dừng):** Đối với các văn bản phức hợp (VD: Văn bản hợp nhất), hệ thống sẽ bóc tách làm 2 trường dữ liệu riêng biệt:
    *   `document_form`: Hình thức văn bản (VĂN BẢN HỢP NHẤT, BẢN SAO...)
    *   `document_type`: Loại văn bản gốc (BỘ LUẬT, LUẬT, NGHỊ ĐỊNH, QUYẾT ĐỊNH, THÔNG TƯ, CHỈ THỊ...)
    *   *Điều kiện dừng khi trích Tên văn bản (Stop Condition):* Bắt đầu thu thập văn bản ngay sau dòng định danh loại văn bản và **dừng thu thập ngay lập tức** khi gặp một trong các điều kiện:
        1. Dòng trống liên tiếp.
        2. Dòng bắt đầu bằng `Số:` hoặc `Số hiệu:`.
        3. Dòng bắt đầu bằng `Căn cứ`.
        4. Gặp một Structural Marker tiếp theo.
        Điều này đảm bảo Tên văn bản được lấy trọn vẹn mà không nuốt nhầm metadata xung quanh.

## 3. Xác định Biên giới Nội dung (Boundary Detection)
*   **Biên giới trên (Top Boundary) & Bẫy Mục lục:** 
    *   Neo bằng marker cấu trúc đầu tiên (PHẦN, CHƯƠNG, MỤC, ĐIỀU) ở đầu dòng.
    *   *Bypass Mục lục (TOC):* Nhận diện thông qua tín hiệu heading "MỤC LỤC", dấu chấm dẫn (`......`), số trang ở cuối dòng (VD: `Chương I ...... 5`), hoặc cụm nhiều dòng marker liên tiếp không có thân văn bản (> 3 dòng). Bỏ qua hoàn toàn vùng này để tìm điểm bắt đầu nội dung thật sự.
*   **Biên giới dưới (Tail Boundary) - *Strict Match*:** 
    *   Neo đầu dòng (`^`), quét ngược từ cuối file lên (vùng cận EOF).
    *   Các Pattern đuôi: `^Nơi nhận:`, `^PHỤ LỤC`, hoặc các chức danh ký duyệt `^(TM\.|KT\.|Q\.)\s+[A-ZÀ-Ỹ]`, `^BỘ TRƯỞNG`, `^THỦ TƯỚNG`.
    *   *Chống cắt lụi vào nội dung (Tín hiệu vị trí & Định dạng thay vì độ dài cứng):* Dòng chức danh ký duyệt được nhận diện dựa trên: (1) Nằm ở đoạn cuối văn bản gần EOF; (2) Toàn dòng viết hoa hoặc theo chuẩn chức danh; (3) Đứng độc lập và tuyệt đối không có dấu chấm/phẩy kết thúc câu (đảm bảo không bị miss các bộ có tên dài như "BỘ TRƯỞNG BỘ LAO ĐỘNG - THƯƠNG BINH VÀ XÃ HỘI" mà vẫn tránh nhầm câu văn thường).

## 4. Tái thiết lập Hệ thống Phân cấp (Structural Transformation)
*   **Độc lập định dạng (Format Agnostic):** Dựa trên text pattern thuần (VD: `^Phần [IVXLC]+`, `^Chương [IVXLC]+`).
*   **Regex "Điều" nới lỏng & Hậu tố:** Pattern linh hoạt: `^Điều\s+\d+[a-z]?[\.:]?`.
*   **Gộp dòng Tiêu đề đồng bộ cho cả 4 cấp (Phần / Chương / Mục / Điều):** Áp dụng cơ chế dò và gộp (merge) dòng định danh với dòng tiêu đề ngay dưới nó cho toàn bộ các cấp để tránh dòng text mồ côi:
    *   `Phần...` + Dòng tên ➡️ `# Phần I. Tên phần`
    *   `Chương...` + Dòng tên ➡️ `## Chương I. Tên chương`
    *   `Mục...` + Dòng tên ➡️ `### Mục 1. Tên mục`
    *   `Điều...` + Dòng tên ➡️ `#### Điều 1. Tên điều`

## 5. Đánh giá tính toàn vẹn (Validation & Sanity Check)
*   **Đếm và so khớp:** Sau khi Parse, hệ thống tự động đếm tổng số lượng `#### Điều` được tạo ra. So sánh với số thứ tự Điều lớn nhất tìm được.
*   **Xử lý Điều bãi bỏ (Repealed Articles):** 
    *   Nếu có placeholder rõ ràng (VD: `Điều 12. (Bãi bỏ)`), hệ thống sẽ không tính là lỗi hụt.
    *   *Known Limitation:* Đối với văn bản hợp nhất xóa hoàn toàn số Điều mà không để lại placeholder, hệ thống sẽ đưa ra mức cảnh báo `WARNING` (thay vì `ERROR`) kèm danh sách các số Điều bị thiếu để reviewer kiểm tra đối chiếu lại với phần "Điều khoản thi hành" hoặc phụ lục sửa đổi.

## 6. Lưu ý khi triển khai mã nguồn (Implementation Nuances)
*   **Tiêu đề dài bị ngắt nhiều dòng:** Khi gộp dòng tiêu đề (Phần/Chương/Mục/Điều), tiếp tục nuốt các dòng kế tiếp cho đến khi gặp dòng trống hoặc ký tự bắt đầu của Khoản (`1.`, `a)`), tránh để phần đuôi của tiêu đề bị trượt xuống body.
*   **Dòng trống giả do Page Break:** Phân biệt dòng trống ngăn cách ngữ nghĩa với dòng ngắt trang ngẫu nhiên (chỉ dừng lấy Tên văn bản khi gặp từ 2 dòng trống liên tiếp hoặc dòng sau chuyển sang cấu trúc mới).
