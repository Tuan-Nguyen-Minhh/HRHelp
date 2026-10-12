import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Scale } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToneBadge } from "@/components/common/StatusBadge";
import { EvidenceDrawer } from "@/features/evidence/EvidenceDrawer";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { evidenceItems } from "@/lib/evidence";
import { HOLD_LABEL, riskLabel, sanctionLabel, statusLabel } from "@/lib/labels";
import { assessmentView, type AssessmentView, visibleSanction } from "@/lib/workflow";
import { placeLabel } from "@/lib/utils";
import type { EvidenceItem } from "@/types/api";

const TONE = {
  collecting: "neutral",
  supported: "success",
  held: "warning",
  review: "danger",
  open: "warning",
  withheld: "warning",
} as const;

export function SanctionAssessment() {
  const { caseId, answer, handoff, caseView, facts, focusChat } = useWorkspace();
  const [selected, setSelected] = useState<EvidenceItem | null>(null);
  const view = assessmentView(caseView.status, answer, facts?.missing_fact_keys.length ?? 0);
  const level = view === "withheld" || view === "collecting" ? null : visibleSanction(answer);
  const support = evidenceItems(answer, handoff, caseView.case_code).filter(
    (item) => item.kind === "LAW" || item.kind === "DECREE" || item.kind === "INTERNAL_RULE",
  );
  const ticket = answer?.ticket ?? null;

  return (
    <Card className={cardClass(view)}>
      <CardHeader>
        <CardTitle>Đánh giá chế tài</CardTitle>
        <ToneBadge tone={TONE[view]} label={viewLabel(view, caseView.status)} />
      </CardHeader>
      <CardContent className="space-y-4">
        {view === "collecting" ? (
          <p className="text-sm text-ink-2">
            Chưa có mức kỷ luật để hiển thị. Trợ lý hỏi phần còn thiếu trong hội thoại, rồi backend mới lưu đánh giá.
          </p>
        ) : null}

        {view === "withheld" ? (
          <Notice
            title="Mức đã lưu không được trình bày"
            body={
              answer?.sanction_type === "TERMINATION"
                ? "Giá trị đã lưu là chấm dứt hợp đồng. Màn hình không trình bày giá trị đó như mức kỷ luật của người lao động."
                : "Báo cáo có một mức đã lưu nhưng không kèm đoạn luật hoặc nội quy."
            }
          />
        ) : null}

        {view === "open" || view === "held" ? (
          <Notice
            title={level ? "Mức đã lưu, phiếu chưa được đẩy" : "Kết quả đánh giá"}
            body={answer?.rationale || ticket?.reason || "Biên bản bên dưới là kết quả để HR xem và chốt."}
            detail={ticket?.hold_code ? `${HOLD_LABEL[ticket.hold_code] ?? ticket.hold_code} · ${ticket.hold_code}` : undefined}
          />
        ) : null}

        {view === "review" ? (
          <div className="flex items-start gap-2">
            <Scale className="mt-0.5 h-4 w-4 shrink-0 text-son-dark" aria-hidden="true" />
            <div>
              <p className="font-medium text-son-dark">{reviewTitle(caseView.status)}</p>
              <p className="text-sm text-ink-2">{ticket?.reason || "Phiếu đã rời khỏi bước soạn của nhân sự."}</p>
            </div>
          </div>
        ) : null}

        {view === "supported" ? (
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ink-2" aria-hidden="true" />
            <p className="text-sm text-ink-2">
              {ticket?.disposition === "PREVIEW"
                ? "Báo cáo đã lưu một mức kèm đoạn luật hoặc nội quy. Phiếu đang ở bước xem trước."
                : "Báo cáo đã lưu một mức kèm đoạn luật hoặc nội quy."}
            </p>
          </div>
        ) : null}

        {level ? (
          <div>
            <p className="text-xs text-ink-3">Mức kỷ luật đã lưu</p>
            <p className="text-lg font-semibold">{sanctionLabel(level)}</p>
            <p className="text-xs text-ink-3">{level}</p>
          </div>
        ) : null}

        {answer && view !== "collecting" ? (
          <div>
            <p className="text-xs text-ink-3">Rủi ro căn cứ</p>
            <p className="text-sm font-medium">
              {riskLabel(answer.risk_level)}
              {answer.risk_level ? ` (${answer.risk_level})` : ""}
            </p>
          </div>
        ) : null}

        {answer && view !== "collecting" ? (
          <div>
            <p className="text-xs text-ink-3">Lý do đã ghi</p>
            <p className="whitespace-pre-wrap text-sm leading-6 text-ink">{answer.rationale || "Chưa có lý do."}</p>
          </div>
        ) : null}

        {answer?.standard?.rule && view !== "collecting" ? (
          <p className="rounded-md border border-rule bg-paper-2 px-3 py-2 text-sm text-ink">{answer.standard.rule}</p>
        ) : null}

        {level && support.length > 0 ? (
          <div>
            <p className="text-xs font-medium text-ink-3">Căn cứ của mức đã lưu</p>
            <ol className="mt-2 space-y-3">
              {support.map((item, index) => (
                <li key={item.id} className="rounded-md border border-rule px-3 py-2">
                  <p className="text-sm font-medium">
                    [{index + 1}] {item.policyName || item.policyCode} {placeLabel(item.article, item.clause, item.point)}
                  </p>
                  <p className="mt-1 line-clamp-3 text-sm text-ink-2">{item.content}</p>
                  <Button className="mt-1 px-0" variant="ghost" size="sm" onClick={() => setSelected(item)}>
                    Xem nguồn
                  </Button>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {view === "collecting" || view === "held" || view === "open" || view === "withheld" ? (
            <Button variant="secondary" onClick={focusChat}>
              Trả lời trong hội thoại
            </Button>
          ) : null}
          {view === "held" || view === "open" || view === "withheld" ? (
            <Button variant="secondary" asChild>
              <a href="#can-cu">Xem căn cứ</a>
            </Button>
          ) : null}
          {view === "supported" ? (
            <Button asChild>
              <Link to={`/cases/${caseId}/decision`}>Tiếp tục quyết định</Link>
            </Button>
          ) : null}
          {view === "review" ? (
            <Button variant="secondary" asChild>
              <Link to={`/cases/${caseId}/legal-review`}>Mở hồ sơ pháp chế</Link>
            </Button>
          ) : null}
        </div>
      </CardContent>
      <EvidenceDrawer item={selected} onClose={() => setSelected(null)} />
    </Card>
  );
}

function Notice({ title, body, detail }: { title: string; body: string; detail?: string }) {
  return (
    <div className="flex items-start gap-2">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-son-dark" aria-hidden="true" />
      <div>
        <p className="font-medium text-son-dark">{title}</p>
        <p className="text-sm text-ink-2">{body}</p>
        {detail ? <p className="mt-1 text-xs text-ink-2">{detail}</p> : null}
      </div>
    </div>
  );
}

function cardClass(view: AssessmentView): string {
  if (view === "review") return "border-son-line";
  if (view === "supported") return "border-leather";
  if (view === "collecting") return "";
  return "border-son-line";
}

function viewLabel(view: AssessmentView, status: string): string {
  if (view === "collecting") return "Đang thu thập tình tiết";
  if (view === "supported") return "Đủ căn cứ để xem phiếu";
  if (view === "held") return "Phiếu đang giữ";
  if (view === "review") return statusLabel(status);
  if (view === "withheld") return "Mức không được trình bày";
  return "Kết quả đánh giá";
}

function reviewTitle(status: string): string {
  if (status === "PENDING_LEGAL") return "Hồ sơ đang ở hàng chờ pháp chế.";
  if (status === "REJECTED") return "Hồ sơ đã được trả lại.";
  if (status === "APPROVED" || status === "DECIDED" || status === "CLOSED") return "Hồ sơ đã qua bước ghi nhận.";
  return "Phiếu đã được đẩy sang pháp chế.";
}
