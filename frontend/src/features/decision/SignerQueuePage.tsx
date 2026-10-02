import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api, errorMessage } from "@/services/api";

export function SignerQueuePage() {
  const query = useQuery({ queryKey: ["cases"], queryFn: () => api.listCases() });
  const rows = (query.data?.cases ?? []).filter((item) => item.status === "APPROVED" || item.status === "DECIDED");
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">NGƯỜI KÝ</p>
        <h1 className="text-2xl font-semibold text-[#073642]">Quyết định</h1>
        <p className="mt-1 text-sm text-[#4d7380]">Mức kỷ luật lấy từ đề xuất pháp chế đã duyệt. Màn hình không cho chọn mức khác.</p>
      </div>
      {query.isLoading ? <p className="text-sm">Đang tải…</p> : null}
      {query.isError ? <p className="text-sm text-red-800">{errorMessage(query.error)}</p> : null}
      {rows.length === 0 && !query.isLoading ? (
        <p className="rounded-xl border border-dashed border-[#9fd0db] bg-white px-4 py-8 text-sm text-[#4d7380]">Chưa có hồ sơ chờ ký hoặc đã ban hành.</p>
      ) : null}
      <ul className="space-y-2">
        {rows.map((item) => (
          <li key={item.case_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#d5e8ed] bg-white px-4 py-3">
            <div>
              <Link className="font-medium text-[#009EC1] underline" to={`/decisions/${item.case_id}`}>
                {item.case_code}
              </Link>
              <p className="text-sm text-[#4d7380]">{item.employee_name}</p>
            </div>
            <span className="text-xs font-medium text-[#073642]">{item.status}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
