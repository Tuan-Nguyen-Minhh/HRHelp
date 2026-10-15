import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useMe } from "@/app/providers";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { familyLabel, statusLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import { api, errorMessage } from "@/services/api";

const STATUSES = ["", "OPEN", "NEED_INFO", "ANALYZED", "PENDING_LEGAL", "APPROVED", "REJECTED", "DECIDED", "CLOSED"];

export function CasesPage() {
  const me = useMe();
  const role = me.data?.role ?? "";
  const canCreate = role === "HR";
  const query = useQuery({ queryKey: ["cases"], queryFn: () => api.listCases() });
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [family, setFamily] = useState("");
  const [incidentDate, setIncidentDate] = useState("");
  const [sort, setSort] = useState<"date" | "code" | "employee">("date");
  const [page, setPage] = useState(0);

  const rows = useMemo(() => {
    const needle = text.trim().toLocaleLowerCase("vi");
    const filtered = (query.data?.cases ?? []).filter((item) => {
      if (status && item.status !== status) return false;
      if (family && item.family !== family) return false;
      if (incidentDate && item.incident_date !== incidentDate) return false;
      if (!needle) return true;
      const blob = `${item.case_code} ${item.employee_name ?? ""} ${item.employee_code ?? ""}`.toLocaleLowerCase("vi");
      return blob.includes(needle);
    });
    filtered.sort((left, right) => {
      if (sort === "code") return left.case_code.localeCompare(right.case_code, "vi");
      if (sort === "employee") return (left.employee_name ?? "").localeCompare(right.employee_name ?? "", "vi");
      return (right.incident_date ?? "").localeCompare(left.incident_date ?? "");
    });
    return filtered;
  }, [query.data, text, status, family, incidentDate, sort]);

  useEffect(() => {
    setPage(0);
  }, [text, status, family, incidentDate, sort]);

  const pageSize = 8;
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const visible = rows.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">HỒ SƠ</p>
          <h1 className="text-2xl font-semibold text-ink">Danh sách vụ việc</h1>
        </div>
      </div>
      <div className="grid gap-3 rounded-xl border border-rule bg-white p-3 md:grid-cols-2 xl:grid-cols-6">
        <div className="min-w-0 space-y-1.5 md:col-span-2">
          <Label htmlFor="case-search">Tìm kiếm</Label>
          <Input id="case-search" value={text} onChange={(event) => setText(event.target.value)} placeholder="Tìm mã hồ sơ hoặc nhân viên" />
        </div>
        <div className="min-w-0 space-y-1.5">
          <Label htmlFor="case-status">Trạng thái</Label>
          <select id="case-status" className="h-10 w-full rounded-md border border-rule bg-white px-2 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
            {STATUSES.map((item) => (
              <option key={item || "all"} value={item}>
                {item ? statusLabel(item) : "Mọi trạng thái"}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-0 space-y-1.5">
          <Label htmlFor="case-family">Nhóm vi phạm</Label>
          <select id="case-family" className="h-10 w-full rounded-md border border-rule bg-white px-2 text-sm" value={family} onChange={(event) => setFamily(event.target.value)}>
            <option value="">Mọi nhóm</option>
            <option value="UNAUTHORIZED_ABSENCE">{familyLabel("UNAUTHORIZED_ABSENCE")}</option>
            <option value="LATE">{familyLabel("LATE")}</option>
            <option value="GENERAL">{familyLabel("GENERAL")}</option>
          </select>
        </div>
        <div className="min-w-0 space-y-1.5">
          <Label htmlFor="case-incident-date">Ngày vi phạm</Label>
          <Input id="case-incident-date" className="min-w-0" type="date" value={incidentDate} onChange={(event) => setIncidentDate(event.target.value)} />
        </div>
        <div className="min-w-0 space-y-1.5">
          <Label htmlFor="case-sort">Sắp xếp</Label>
          <select id="case-sort" className="h-10 w-full rounded-md border border-rule bg-white px-2 text-sm" value={sort} onChange={(event) => setSort(event.target.value as "date" | "code" | "employee")}>
            <option value="date">Ngày vi phạm mới nhất</option>
            <option value="code">Mã hồ sơ</option>
            <option value="employee">Tên nhân viên</option>
          </select>
        </div>
      </div>
      {query.isLoading ? (
        <div className="space-y-2 rounded-xl border border-rule bg-white p-3" role="status" aria-label="Đang tải hồ sơ">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton h-10" aria-hidden="true" />
          ))}
        </div>
      ) : null}
      {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
      {!query.isLoading && !query.isError && rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-rule-2 bg-white px-4 py-8 text-sm text-ink-3">
          Không có hồ sơ khớp bộ lọc.
          {canCreate ? (
            <Link className="ml-2 font-medium text-son-dark underline" to="/cases/new">
              Tạo hồ sơ mới
            </Link>
          ) : null}
        </div>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-rule bg-white">
        <table className="min-w-full text-left text-sm uppercase">
          <thead className="bg-paper-2 text-xs uppercase tracking-wide text-ink-3">
            <tr>
              <th className="px-3 py-2">Mã</th>
              <th className="px-3 py-2">Nhân viên</th>
              <th className="px-3 py-2">Nhóm</th>
              <th className="px-3 py-2">Ngày vi phạm</th>
              <th className="px-3 py-2">Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.case_id} className="border-t border-rule">
                <td className="px-3 py-2">
                  <Link className="font-medium text-son-dark underline" to={`/cases/${item.case_id}`}>
                    {item.case_code}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  <p>{item.employee_name || "—"}</p>
                  <p className="text-xs text-ink-3">{item.employee_code}</p>
                </td>
                <td className="px-3 py-2">{familyLabel(item.family)}</td>
                <td className="px-3 py-2">{formatDate(item.incident_date)}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={item.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > pageSize ? (
        <div className="flex items-center justify-between text-sm text-ink-3">
          <span>
            {page + 1} / {pageCount}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={page === 0} onClick={() => setPage((current) => current - 1)}>
              Trước
            </Button>
            <Button variant="secondary" disabled={page + 1 >= pageCount} onClick={() => setPage((current) => current + 1)}>
              Sau
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
