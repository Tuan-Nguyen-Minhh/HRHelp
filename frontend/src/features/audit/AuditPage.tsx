import { Link } from "react-router-dom";

export function AuditPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-3">
      <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">NHẬT KÝ</p>
      <h1 className="text-2xl font-semibold text-[#073642]">Dấu vết theo từng hồ sơ</h1>
      <p className="text-sm leading-6 text-[#355861]">
        Audit là bản ghi chỉ thêm, không có màn sửa hay xóa. Mỗi hồ sơ ghép tin nhắn, lần chạy agent, đề xuất, duyệt và quyết định tại dòng thời gian.
      </p>
      <Link className="inline-block text-sm font-medium text-[#009EC1] underline" to="/cases">
        Chọn hồ sơ để xem dòng thời gian
      </Link>
    </div>
  );
}
