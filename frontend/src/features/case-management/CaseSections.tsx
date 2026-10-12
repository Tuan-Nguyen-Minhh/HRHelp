import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AssessmentForm } from "@/features/assessment/form/AssessmentForm";
import { ConversationPanel } from "@/features/conversation/ConversationPanel";
import { RecidivismPanel } from "@/features/case-management/RecidivismPanel";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { DraftList } from "@/features/decision/DraftList";
import { EvidencePanel } from "@/features/evidence/EvidencePanel";
import { FactPanel } from "@/features/evidence/FactPanel";
import { MissingFactCard } from "@/features/evidence/MissingFactCard";
import { RetrievalPanel } from "@/features/evidence/RetrievalPanel";
import { TimelinePanel } from "@/features/timeline/TimelinePanel";

export function ConversationPage() {
  return <ConversationPanel />;
}

export function FactsPage() {
  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <FactPanel />
      <div className="space-y-4">
        <MissingFactCard />
        <RecidivismPanel />
      </div>
    </div>
  );
}

export function EvidencePage() {
  return (
    <div className="space-y-4">
      <RetrievalPanel />
      <EvidencePanel />
    </div>
  );
}

export function DocumentsPage() {
  const { answer, answerLoading, answerError } = useWorkspace();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Văn bản xem trước</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-ink-3">
          Biên bản đánh giá, yêu cầu giải trình, dự thảo quyết định và phiếu chuyển pháp chế. Chỉ hiện bản backend đã lưu.
        </p>
        {answerLoading ? <p className="text-sm text-ink-3">Đang tải văn bản…</p> : null}
        {answerError ? <p className="text-sm text-son-dark">{answerError}</p> : null}
        <DraftList drafts={answer?.drafts ?? []} />
      </CardContent>
    </Card>
  );
}

export function AssessmentPage() {
  return <AssessmentForm />;
}

export function TimelinePage() {
  return <TimelinePanel />;
}
