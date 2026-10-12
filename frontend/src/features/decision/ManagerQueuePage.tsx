import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { StaffAccounts } from "@/features/accounts/StaffAccounts";
import { formatDate } from "@/lib/utils";
import { api, errorMessage } from "@/services/api";

export function ManagerQueuePage() {
  const query = useQuery({ queryKey: ["manager-queue"], queryFn: () => api.managerQueue() });
  const rows = query.data?.cases ?? [];
  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">QUẢN LÝ</p>
        <h1 className="text-2xl font-semibold text-ink">Duyệt lần cuối</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-3">
          Hồ sơ pháp chế đã duyệt, hoặc HR chuyển thẳng. Mức kỷ luật lấy từ báo cáo đã lưu. Quản lý không chọn mức khác.
        </p>
      </div>
      {query.isLoading ? (<div className="space-y-2" role="status" aria-label="Đang tải hàng chờ">{Array.from({ length: 4 }).map((_, i) => (<div key={i} className="skeleton h-12" aria-hidden="true" />))}</div>) : null}
      {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
      {!query.isLoading && !query.isError && rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule-2 bg-white px-4 py-8 text-sm text-ink-3">
          Không có hồ sơ chờ duyệt cuối.
        </p>
      ) : null}
      <ul className="space-y-2">
        {rows.map((item) => (
          <li key={item.case_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-rule bg-white px-4 py-3">
            <div>
              <Link className="font-medium text-son-dark underline" to={`/manager/${item.case_id}`}>
                {item.case_code}
              </Link>
              <p className="text-sm text-ink-3">
                {item.employee_name || "Chưa có tên"} · {formatDate(item.incident_date)}
              </p>
            </div>
            <span className="text-xs font-medium text-ink">Chờ duyệt cuối</span>
          </li>
        ))}
      </ul>
      <StaffAccounts />
    </div>
  );
}
