import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AssessmentForm } from "@/features/assessment/form/AssessmentForm";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { HOLD_LABEL, statusLabel } from "@/lib/labels";

export function LegalReviewPage() {
  const { caseView, answer } = useWorkspace();
  const ticket = answer?.ticket ?? null;
  const queued = caseView.status === "PENDING_LEGAL";
  const atManager = caseView.status === "APPROVED";
  const completed = caseView.status === "DECIDED" || caseView.status === "CLOSED";
  const description = queued
    ? "Đã gửi thành công. Hồ sơ đang ở hàng chờ pháp chế."
    : atManager
      ? "Hồ sơ đã chuyển sang quản lý để duyệt lần cuối."
      : caseView.status === "REJECTED"
        ? "Hồ sơ đã trả về HR. Mở lại hồ sơ để bổ sung và gửi lại."
        : completed
          ? `Hồ sơ đã hoàn tất bước duyệt. Trạng thái: ${statusLabel(caseView.status)}.`
          : "Xem, lưu chỉnh sửa và xác nhận biên bản bên dưới, sau đó chọn email pháp chế để gửi phiếu.";

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <Card className={queued ? "border-son-line" : ""}>
        <CardHeader><CardTitle>Gói duyệt pháp chế</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="font-medium" role="status">{description}</p>
          {ticket?.reason ? <p>{ticket.reason}</p> : null}
          {ticket?.hold_code ? <p className="text-xs text-ink-3">{HOLD_LABEL[ticket.hold_code] ?? ticket.hold_code}</p> : null}
        </CardContent>
      </Card>
      <AssessmentForm />
    </div>
  );
}
