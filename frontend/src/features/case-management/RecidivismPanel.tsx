import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { sanctionLabel, statusLabel } from "@/lib/labels";
import { MUTABLE_CASE_STATUS } from "@/lib/workflow";
import { api, errorMessage } from "@/services/api";

export function RecidivismPanel() {
  const { caseId, caseView } = useWorkspace();
  const editable = MUTABLE_CASE_STATUS.has(caseView.status);
  const lookup = useMutation({ mutationFn: () => api.recidivism(caseId) });
  const report = lookup.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Vụ việc trước</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-ink-3">
          Các vụ cùng mã nhân viên chỉ là lịch sử. Chúng không tự quyết mức kỷ luật của vụ này. HR xác nhận nếu thấy liên quan.
        </p>
        {editable ? (
          <Button variant="secondary" disabled={lookup.isPending} onClick={() => lookup.mutate()}>
            {lookup.isPending ? "Đang đối chiếu…" : "Xem vụ trước"}
          </Button>
        ) : (
          <p className="text-ink-3">Hồ sơ không còn nhận thêm xác nhận tình tiết.</p>
        )}
        {lookup.isError ? <p className="text-son-dark">{errorMessage(lookup.error)}</p> : null}
        {report && report.prior_cases.length === 0 ? <p>Không thấy vụ trước với mã nhân viên này.</p> : null}
        {report && report.prior_cases.length > 0 ? (
          <div className="space-y-2">
            <p className="rounded-md bg-paper-2 px-3 py-2 text-ink">
              Đã thấy {report.prior_cases.length} vụ trước. Chưa dùng để chốt mức.{" "}
              {report.confirmed ? "HR đã xác nhận số lần." : "Chưa xác nhận."}
            </p>
            <ul className="space-y-2">
              {report.prior_cases.map((item) => (
                <li key={item.case_id} className="rounded-lg border border-rule px-3 py-2">
                  <p className="font-medium text-ink">{item.case_code}</p>
                  <p className="text-xs text-ink-3">{statusLabel(item.status)}</p>
                </li>
              ))}
            </ul>
            {report.prior_decisions.length > 0 ? (
              <ul className="space-y-1 text-xs text-ink-2">
                {report.prior_decisions.map((item) => (
                  <li key={item.decision_code}>
                    {item.decision_code} · {sanctionLabel(item.sanction_type)} · {new Date(item.issued_at).toLocaleDateString("vi-VN")}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
