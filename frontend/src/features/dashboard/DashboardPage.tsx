import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useMe } from "@/app/providers";
import { StatusBadge, ToneBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LegalQueueTable } from "@/features/legal-review/LegalQueueTable";
import { CASE_STATUSES, familyLabel, statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import { api, errorMessage } from "@/services/api";

export function DashboardPage() {
  const me = useMe();
  const role = me.data?.role ?? "";
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const caseListRef = useRef<HTMLDivElement>(null);
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
  const allCases = cases.data?.cases ?? [];
  const filteredCases = allCases.filter((item) => !statusFilter || item.status === statusFilter);
  const pageCount = Math.max(1, Math.ceil(filteredCases.length / 8));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleCases = role === "HR" ? filteredCases.slice(currentPage * 8, (currentPage + 1) * 8) : recent;
  const pendingDecisions = (cases.data?.cases ?? []).filter((item) => item.status === "APPROVED");

  function filterCases(status: string, scroll = false) {
    setStatusFilter((current) => current === status ? "" : status);
    setPage(0);
    if (scroll) caseListRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">BẢNG ĐIỀU KHIỂN</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">Việc cần người xử lý</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-3">
          Số liệu lấy từ hồ sơ bạn được xem. AI không duyệt, không ký và không đóng vụ.
        </p>
      </div>

      {canSummary && summary.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Đang tải số liệu">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton h-[76px]" aria-hidden="true" />
          ))}
        </div>
      ) : null}
      {canSummary && summary.isError ? <p className="text-sm text-son-dark">{errorMessage(summary.error)}</p> : null}

      {canSummary && summary.data ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {CASE_STATUSES.map((status) => (
            <Card key={status} className={role === "HR" && statusFilter === status ? "border-son bg-son-tint" : undefined}>
              {role === "HR" ? (
                <button type="button" className="block w-full rounded-xl px-5 py-4 text-left transition-colors hover:bg-paper-2" aria-pressed={statusFilter === status} aria-controls="hr-case-list" onClick={() => filterCases(status, true)}>
                  <span className="block text-xs text-ink-3">{statusLabel(status)}</span>
                  <span className="mt-1 block text-2xl font-semibold text-ink">{counts[status] ?? 0}</span>
                </button>
              ) : (
                <CardContent className="py-4">
                  <p className="text-xs text-ink-3">{statusLabel(status)}</p>
                  <p className="mt-1 text-2xl font-semibold text-ink">{counts[status] ?? 0}</p>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      ) : null}

      {role === "LEGAL" ? (
        <Card>
          <CardHeader>
            <CardTitle>Hàng chờ pháp chế</CardTitle>
          </CardHeader>
          <CardContent className="overflow-hidden rounded-b-xl p-0">
            <LegalQueueTable rows={queue.data?.reviews ?? []} loading={queue.isLoading} error={queue.isError ? errorMessage(queue.error) : null} />
          </CardContent>
        </Card>
      ) : null}

      {role === "MANAGER" ? (
        <Card>
          <CardHeader>
            <CardTitle>Chờ duyệt cuối</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto rounded-b-xl">
              <table className="w-full min-w-[44rem] text-left text-sm" aria-label="Hồ sơ chờ duyệt cuối">
                <thead className="border-b border-rule bg-paper-2 text-xs font-semibold tracking-wide text-ink-3">
                  <tr>
                    <th scope="col" className="px-5 py-3">Mã hồ sơ</th>
                    <th scope="col" className="px-5 py-3">Nhân viên</th>
                    <th scope="col" className="px-5 py-3">Ngày xảy ra</th>
                    <th scope="col" className="px-5 py-3">Trạng thái</th>
                    <th scope="col" className="px-5 py-3 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {managerQueue.isLoading ? (
                    <tr><td colSpan={5} className="px-5 py-5"><div className="skeleton h-10" role="status" aria-label="Đang tải hàng chờ" /></td></tr>
                  ) : managerQueue.isError ? (
                    <tr><td colSpan={5} className="px-5 py-6 text-son-dark" role="alert">{errorMessage(managerQueue.error)}</td></tr>
                  ) : (managerQueue.data?.cases ?? []).length === 0 ? (
                    <tr><td colSpan={5} className="px-5 py-8 text-center text-ink-3">Không có hồ sơ chờ quản lý.</td></tr>
                  ) : (managerQueue.data?.cases ?? []).map((item) => (
                    <tr key={item.case_id} className="border-b border-rule last:border-0 hover:bg-paper">
                      <td className="px-5 py-4 font-medium uppercase">
                        <Link className="text-son-dark underline" to={`/manager/${item.case_id}`}>{item.case_code}</Link>
                      </td>
                      <td className="px-5 py-4">
                        <p className="font-medium uppercase text-ink">{item.employee_name || "Chưa có tên"}</p>
                        {item.employee_code ? <p className="mt-0.5 text-xs uppercase text-ink-3">{item.employee_code}</p> : null}
                      </td>
                      <td className="whitespace-nowrap px-5 py-4 text-ink-3">{formatDate(item.incident_date)}</td>
                      <td className="whitespace-nowrap px-5 py-4"><ToneBadge tone="warning" label="Chờ duyệt cuối" /></td>
                      <td className="px-5 py-4 text-right">
                        <Button asChild variant="secondary" size="sm"><Link to={`/manager/${item.case_id}`}>Xem hồ sơ</Link></Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {role === "SIGNER" ? (
        <Card>
          <CardHeader>
            <CardTitle>Chờ ban hành</CardTitle>
          </CardHeader>
          <CardContent>
            {pendingDecisions.length === 0 ? <p className="text-sm text-ink-3">Chưa có hồ sơ đã duyệt để ký.</p> : null}
            <ul className="space-y-2 uppercase">
              {pendingDecisions.map((item) => (
                <li key={item.case_id}>
                  <Link className="font-medium text-son-dark underline" to={`/decisions/${item.case_id}`}>
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
              <span key={family} className="rounded-full bg-paper-2 px-3 py-1 text-ink">
                {familyLabel(family)} · {count}
              </span>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {role === "HR" || recent.length > 0 ? (
        <Card id="hr-case-list" className="scroll-mt-24">
          <div ref={caseListRef} className="scroll-mt-24" />
          <CardHeader>
            <div>
              <CardTitle>{role === "HR" ? "Hồ sơ HR" : "Hồ sơ gần đây"}</CardTitle>
              {role === "HR" ? <p className="mt-1 text-sm text-ink-3" role="status">{filteredCases.length} hồ sơ{statusFilter ? ` · ${statusLabel(statusFilter)}` : " · Tất cả trạng thái"}</p> : null}
            </div>
            {role === "HR" ? <Link className="text-sm font-medium text-son-dark underline" to={statusFilter ? `/cases?status=${statusFilter}` : "/cases"}>Mở danh sách đầy đủ</Link> : null}
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto rounded-b-xl">
              <table className="w-full min-w-[36rem] table-fixed text-left text-sm uppercase" aria-label={role === "HR" ? "Hồ sơ HR theo trạng thái" : "Hồ sơ gần đây"}>
                <colgroup>
                  <col className="w-1/4" />
                  <col className="w-[45%]" />
                  <col className="w-[30%]" />
                </colgroup>
                <thead className="border-b border-rule bg-paper-2 text-xs tracking-wide text-ink-3">
                  <tr>
                    <th scope="col" className="px-5 py-3">Mã hồ sơ</th>
                    <th scope="col" className="px-5 py-3">Nhân viên</th>
                    <th scope="col" className="px-5 py-3">Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {role === "HR" && cases.isLoading ? (
                    <tr><td colSpan={3} className="px-5 py-5"><div className="skeleton h-12" role="status" aria-label="Đang tải hồ sơ" /></td></tr>
                  ) : role === "HR" && cases.isError ? (
                    <tr><td colSpan={3} className="px-5 py-6 text-son-dark" role="alert">{errorMessage(cases.error)}</td></tr>
                  ) : visibleCases.length === 0 ? (
                    <tr><td colSpan={3} className="px-5 py-8 text-center normal-case text-ink-3">Không có hồ sơ{statusFilter ? ` ở trạng thái “${statusLabel(statusFilter)}”` : ""}.</td></tr>
                  ) : visibleCases.map((item) => (
                    <tr key={item.case_id} className="border-b border-rule last:border-0">
                      <td className="break-words px-5 py-3 align-middle">
                        <Link className="font-medium text-ink underline" to={`/cases/${item.case_id}`}>
                          {item.case_code}
                        </Link>
                      </td>
                      <td className="break-words px-5 py-3 align-middle text-ink-3">{item.employee_name || "Chưa có tên"}</td>
                      <td className="px-5 py-3 align-middle">
                        <StatusBadge status={item.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
          {role === "HR" && !cases.isLoading && !cases.isError && filteredCases.length > 8 ? (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-5 py-3 text-sm text-ink-3">
              <span>Trang {currentPage + 1} / {pageCount} · {filteredCases.length} hồ sơ</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Trước</Button>
                <Button variant="secondary" size="sm" disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Sau</Button>
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
