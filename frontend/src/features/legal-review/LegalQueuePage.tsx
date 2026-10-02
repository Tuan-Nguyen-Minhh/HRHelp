import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { formatDate } from "@/lib/utils";
import { api, errorMessage } from "@/services/api";

export function LegalQueuePage() {
  const query = useQuery({ queryKey: ["legal-queue"], queryFn: () => api.legalQueue() });
  const rows = query.data?.reviews ?? [];
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">PHÁP CHẾ</p>
        <h1 className="text-2xl font-semibold text-[#073642]">Phiếu đang chờ duyệt</h1>
        <p className="mt-1 text-sm text-[#4d7380]">Mọi phiếu HR vừa gửi. Duyệt để chuyển quản lý, hoặc yêu cầu HR xử lý lại.</p>
      </div>
      {query.isLoading ? <p className="text-sm">Đang tải hàng chờ…</p> : null}
      {query.isError ? <p className="text-sm text-red-800">{errorMessage(query.error)}</p> : null}
      {!query.isLoading && rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-[#9fd0db] bg-white px-4 py-8 text-sm text-[#4d7380]">Không có phiếu chờ duyệt.</p>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-[#d5e8ed] bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-[#e7f6f9] text-xs uppercase text-[#4d7380]">
            <tr>
              <th className="px-3 py-2">Hồ sơ</th>
              <th className="px-3 py-2">Nhân viên</th>
              <th className="px-3 py-2">Ngày vụ</th>
              <th className="px-3 py-2">Cập nhật</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.case_id} className="border-t border-[#eef6f8]">
                <td className="px-3 py-2">
                  <Link className="font-medium text-[#009EC1] underline" to={`/legal-review/${item.case_id}`}>
                    {item.case_code}
                  </Link>
                </td>
                <td className="px-3 py-2">{item.employee_name || "—"}</td>
                <td className="px-3 py-2">{formatDate(item.incident_date)}</td>
                <td className="px-3 py-2">{new Date(item.updated_at).toLocaleString("vi-VN")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
