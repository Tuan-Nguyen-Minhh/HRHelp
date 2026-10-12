import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { DraftList } from "@/features/decision/DraftList";
import { LegalTicketCard } from "@/features/decision/LegalTicketCard";
import { HOLD_LABEL, TICKET_LABEL, riskLabel, sanctionLabel } from "@/lib/labels";
import { visibleSanction } from "@/lib/workflow";
import { api } from "@/services/api";
import { formatDate } from "@/lib/utils";

export function DecisionPage() {
  const { caseView, answer, caseId } = useWorkspace();
  const level = visibleSanction(answer);
  const supportCount = (answer?.legal_basis.length ?? 0) + (answer?.internal_rule.length ?? 0);
  const assessment = useQuery({ queryKey: ["assessment", caseId], queryFn: () => api.getAssessment(caseId) });
  const ticket = answer?.ticket ?? null;
  const formConfirmed = assessment.data?.status === "CONFIRMED";
  const canSend = assessment.data?.permissions.can_create_ticket === true;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Quyết định hồ sơ</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Item label="Nhân viên" value={caseView.employee_name || "—"} />
            <Item label="Ngày xảy ra" value={formatDate(caseView.incident_date)} />
            <Item label="Sự việc" value={caseView.description || "—"} />
            <Item label="Mức trên báo cáo" value={level ? `${sanctionLabel(level)} (${level})` : "Chưa trình bày mức"} />
            <Item label="Rủi ro căn cứ" value={answer ? `${riskLabel(answer.risk_level)} ${answer.risk_level ?? ""}`.trim() : "Chưa có báo cáo"} />
            <Item label="Đoạn luật và nội quy" value={String(supportCount)} />
            <Item label="Bước thủ tục" value={String(answer?.process_steps.length ?? 0)} />
          </dl>
          {answer?.sanction_type && !level ? (
            <p className="rounded-md border border-son-line bg-son-tint px-3 py-2 text-son-dark">
              {answer.sanction_type === "TERMINATION"
                ? "Giá trị đã lưu là chấm dứt hợp đồng. Màn hình không trình bày giá trị đó như mức kỷ luật."
                : "Báo cáo có mức đã lưu nhưng không kèm đoạn luật hoặc nội quy. Mức không được trình bày như đề xuất."}
            </p>
          ) : null}
          {ticket ? (
            <div className="rounded-md border border-rule px-3 py-2">
              <p className="text-xs font-semibold tracking-wide text-ink-3">{TICKET_LABEL[ticket.disposition] ?? ticket.disposition}</p>
              <p className="mt-1">{ticket.reason}</p>
              {ticket.hold_code ? <p className="mt-1 text-xs text-ink-3">{HOLD_LABEL[ticket.hold_code] ?? ticket.hold_code}</p> : null}
            </div>
          ) : (
            <p className="text-ink-2">Chưa có trạng thái phiếu. Nút đẩy chỉ hiện khi backend trả PREVIEW.</p>
          )}
          {assessment.isLoading ? (<div className="skeleton h-12" role="status" aria-label="Đang kiểm tra biên bản" />) : null}
          <LegalTicketCard
            canSend={canSend}
            waitForMinutes={!assessment.isLoading && !formConfirmed && (ticket?.disposition === "PREVIEW" || ticket?.disposition === "HOLD")}
          />
          <div className="flex flex-wrap gap-4 text-sm">
            <Link className="underline" to={`/cases/${caseId}`}>
              Về hồ sơ
            </Link>
            {caseView.status === "PENDING_LEGAL" || caseView.status === "REJECTED" ? (
              <Link className="underline" to={`/cases/${caseId}/legal-review`}>
                Xem phiếu đã gửi
              </Link>
            ) : null}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Bản thảo</CardTitle>
        </CardHeader>
        <CardContent>
          <DraftList drafts={answer?.drafts ?? []} />
        </CardContent>
      </Card>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="whitespace-pre-wrap font-medium">{value}</dd>
    </div>
  );
}
