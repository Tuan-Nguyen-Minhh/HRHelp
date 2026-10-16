import { Link } from "react-router-dom";

import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import type { QueueItem } from "@/types/api";

export function LegalQueueTable({ rows, loading, error, showUpdated = false }: {
  rows: QueueItem[];
  loading: boolean;
  error: string | null;
  showUpdated?: boolean;
}) {
  const columns = showUpdated ? 6 : 5;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] text-left text-sm" aria-label="Hồ sơ chờ pháp chế">
        <thead className="border-b border-rule bg-paper-2 text-xs font-semibold tracking-wide text-ink-3">
          <tr>
            <th scope="col" className="px-5 py-3">Mã hồ sơ</th>
            <th scope="col" className="px-5 py-3">Nhân viên</th>
            <th scope="col" className="px-5 py-3">Ngày xảy ra</th>
            {showUpdated ? <th scope="col" className="px-5 py-3">Cập nhật</th> : null}
            <th scope="col" className="px-5 py-3">Trạng thái</th>
            <th scope="col" className="px-5 py-3 text-right">Thao tác</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={columns} className="px-5 py-5"><div className="skeleton h-10" role="status" aria-label="Đang tải hàng chờ pháp chế" /></td></tr>
          ) : error ? (
            <tr><td colSpan={columns} className="px-5 py-6 text-son-dark" role="alert">{error}</td></tr>
          ) : rows.length === 0 ? (
            <tr><td colSpan={columns} className="px-5 py-8 text-center text-ink-3">Không có phiếu chờ pháp chế.</td></tr>
          ) : rows.map((item) => (
            <tr key={item.case_id} className="border-b border-rule last:border-0 hover:bg-paper">
              <td className="px-5 py-4 font-medium uppercase">
                <Link className="text-son-dark underline" to={`/legal-review/${item.case_id}`}>{item.case_code}</Link>
              </td>
              <td className="px-5 py-4">
                <p className="font-medium uppercase text-ink">{item.employee_name || "Chưa có tên"}</p>
                {item.employee_code ? <p className="mt-0.5 text-xs uppercase text-ink-3">{item.employee_code}</p> : null}
              </td>
              <td className="whitespace-nowrap px-5 py-4 text-ink-3">{formatDate(item.incident_date)}</td>
              {showUpdated ? <td className="whitespace-nowrap px-5 py-4 text-ink-3">{new Date(item.updated_at).toLocaleString("vi-VN")}</td> : null}
              <td className="whitespace-nowrap px-5 py-4"><StatusBadge status={item.status} /></td>
              <td className="px-5 py-4 text-right">
                <Button asChild variant="secondary" size="sm"><Link to={`/legal-review/${item.case_id}`}>Xem hồ sơ</Link></Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
