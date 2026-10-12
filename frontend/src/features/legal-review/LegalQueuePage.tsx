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
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">PHÁP CHẾ</p>
        <h1 className="text-2xl font-semibold text-ink">Phiếu đang chờ duyệt</h1>
        <p className="mt-1 text-sm text-ink-3">Mọi phiếu HR vừa gửi. Duyệt để chuyển quản lý, hoặc yêu cầu HR xử lý lại.</p>
      </div>
      {query.isLoading ? (<div className="space-y-2 rounded-xl border border-rule bg-white p-3" role="status" aria-label="Đang tải hàng chờ">{Array.from({ length: 4 }).map((_, i) => (<div key={i} className="skeleton h-10" aria-hidden="true" />))}</div>) : null}
      {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
      {!query.isLoading && rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule-2 bg-white px-4 py-8 text-sm text-ink-3">Không có phiếu chờ duyệt.</p>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-rule bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-paper-2 text-xs uppercase text-ink-3">
            <tr>
              <th className="px-3 py-2">Hồ sơ</th>
              <th className="px-3 py-2">Nhân viên</th>
              <th className="px-3 py-2">Ngày vụ</th>
              <th className="px-3 py-2">Cập nhật</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.case_id} className="border-t border-rule">
                <td className="px-3 py-2">
                  <Link className="font-medium text-son-dark underline" to={`/legal-review/${item.case_id}`}>
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
