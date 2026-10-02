import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useMe } from "@/app/providers";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { familyLabel, statusLabel } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";

const STATUS_ORDER = ["OPEN", "NEED_INFO", "ANALYZED", "PENDING_LEGAL", "APPROVED", "REJECTED", "DECIDED", "CLOSED"];

export function DashboardPage() {
  const me = useMe();
  const role = me.data?.role ?? "";
  const canSummary = role === "HR" || role === "MANAGER" || role === "ADMIN";
  const summary = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.dashboardSummary(),
    enabled: canSummary,
  });
  const cases = useQuery({
    queryKey: ["cases"],
    queryFn: () => api.listCases(),
    enabled: role === "HR" || role === "MANAGER" || role === "SIGNER" || role === "ADMIN",
  });
  const queue = useQuery({
    queryKey: ["legal-queue"],
    queryFn: () => api.legalQueue(),
    enabled: role === "LEGAL",
  });
  const managerQueue = useQuery({
    queryKey: ["manager-queue"],
    queryFn: () => api.managerQueue(),
    enabled: role === "MANAGER",
  });

  const counts = summary.data?.cases_by_status ?? {};
  const recent = (cases.data?.cases ?? []).slice(0, 6);
  const pendingDecisions = (cases.data?.cases ?? []).filter((item) => item.status === "APPROVED");

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">BẢNG ĐIỀU KHIỂN</p>
        <h1 className="mt-1 text-2xl font-semibold text-[#073642]">Việc cần người xử lý</h1>
        <p className="mt-1 max-w-2xl text-sm text-[#4d7380]">
          Số liệu lấy từ hồ sơ bạn được xem. AI không duyệt, không ký và không đóng vụ.
        </p>
      </div>

      {canSummary && summary.isLoading ? <p className="text-sm text-[#4d7380]">Đang tải số liệu…</p> : null}
      {canSummary && summary.isError ? <p className="text-sm text-red-800">{errorMessage(summary.error)}</p> : null}

      {canSummary && summary.data ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {STATUS_ORDER.map((status) => (
            <Card key={status}>
              <CardContent className="py-4">
                <p className="text-xs text-[#4d7380]">{statusLabel(status)}</p>
                <p className="mt-1 text-2xl font-semibold text-[#073642]">{counts[status] ?? 0}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {role === "LEGAL" ? (
        <Card>
          <CardHeader>
            <CardTitle>Hàng chờ pháp chế</CardTitle>
          </CardHeader>
          <CardContent>
            {queue.isLoading ? <p className="text-sm">Đang tải hàng chờ…</p> : null}
            {queue.data && queue.data.reviews.length === 0 ? (
              <p className="text-sm text-[#4d7380]">Không có phiếu chờ pháp chế.</p>
            ) : null}
            <ul className="space-y-2">
              {(queue.data?.reviews ?? []).map((item) => (
                <li key={item.case_id}>
                  <Link className="font-medium text-[#009EC1] underline" to={`/legal-review/${item.case_id}`}>
                    {item.case_code}
                  </Link>
                  <span className="ml-2 text-sm text-[#4d7380]">{item.employee_name || "Chưa có tên"}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {role === "MANAGER" ? (
        <Card>
          <CardHeader>
            <CardTitle>Chờ duyệt cuối</CardTitle>
          </CardHeader>
          <CardContent>
            {managerQueue.isLoading ? <p className="text-sm">Đang tải hàng chờ…</p> : null}
            {managerQueue.data && managerQueue.data.cases.length === 0 ? (
              <p className="text-sm text-[#4d7380]">Không có hồ sơ chờ quản lý.</p>
            ) : null}
            <ul className="space-y-2">
              {(managerQueue.data?.cases ?? []).map((item) => (
                <li key={item.case_id}>
                  <Link className="font-medium text-[#009EC1] underline" to={`/manager/${item.case_id}`}>
                    {item.case_code}
                  </Link>
                  <span className="ml-2 text-sm text-[#4d7380]">{item.employee_name || "Chưa có tên"}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {role === "SIGNER" ? (
        <Card>
          <CardHeader>
            <CardTitle>Chờ ban hành</CardTitle>
          </CardHeader>
          <CardContent>
            {pendingDecisions.length === 0 ? <p className="text-sm text-[#4d7380]">Chưa có hồ sơ đã duyệt để ký.</p> : null}
            <ul className="space-y-2">
              {pendingDecisions.map((item) => (
                <li key={item.case_id}>
                  <Link className="font-medium text-[#009EC1] underline" to={`/decisions/${item.case_id}`}>
                    {item.case_code}
                  </Link>
                  <span className="ml-2 text-sm">{item.employee_name}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {canSummary && summary.data ? (
        <Card>
          <CardHeader>
            <CardTitle>Theo nhóm vụ</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3 text-sm">
            {Object.entries(summary.data.cases_by_family).length === 0 ? <p>Chưa có nhóm.</p> : null}
            {Object.entries(summary.data.cases_by_family).map(([family, count]) => (
              <span key={family} className="rounded-full bg-[#e7f6f9] px-3 py-1 text-[#073642]">
                {familyLabel(family)} · {count}
              </span>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {recent.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Hồ sơ gần đây</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {recent.map((item) => (
              <div key={item.case_id} className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e5f1f4] py-2 last:border-0">
                <Link className="font-medium text-[#073642] underline" to={`/cases/${item.case_id}`}>
                  {item.case_code}
                </Link>
                <span className="text-sm text-[#4d7380]">{item.employee_name}</span>
                <StatusBadge status={item.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
