import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api, errorMessage } from "@/services/api";

export function SignerQueuePage() {
  const query = useQuery({ queryKey: ["cases"], queryFn: () => api.listCases() });
  const rows = (query.data?.cases ?? []).filter((item) => item.status === "APPROVED" || item.status === "DECIDED");
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">NGƯỜI KÝ</p>
        <h1 className="text-2xl font-semibold text-ink">Quyết định</h1>
        <p className="mt-1 text-sm text-ink-3">Mức kỷ luật lấy từ đề xuất pháp chế đã duyệt. Màn hình không cho chọn mức khác.</p>
      </div>
      {query.isLoading ? (<div className="space-y-2" role="status" aria-label="Đang tải">{Array.from({ length: 4 }).map((_, i) => (<div key={i} className="skeleton h-12" aria-hidden="true" />))}</div>) : null}
      {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
      {rows.length === 0 && !query.isLoading ? (
        <p className="rounded-xl border border-dashed border-rule-2 bg-white px-4 py-8 text-sm text-ink-3">Chưa có hồ sơ chờ ký hoặc đã ban hành.</p>
      ) : null}
      <ul className="space-y-2">
        {rows.map((item) => (
          <li key={item.case_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-rule bg-white px-4 py-3">
            <div>
              <Link className="font-medium text-son-dark underline" to={`/decisions/${item.case_id}`}>
                {item.case_code}
              </Link>
              <p className="text-sm text-ink-3">{item.employee_name}</p>
            </div>
            <span className="text-xs font-medium text-ink">{item.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
