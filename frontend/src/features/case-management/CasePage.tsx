import { AssessmentEntry } from "@/features/assessment/form/AssessmentForm";
import { CaseOverview } from "@/features/case-management/CaseOverview";
import { RecidivismPanel } from "@/features/case-management/RecidivismPanel";
import { ConversationPanel } from "@/features/conversation/ConversationPanel";
import { EvidencePanel } from "@/features/evidence/EvidencePanel";
import { FactPanel } from "@/features/evidence/FactPanel";
import { MissingFactCard } from "@/features/evidence/MissingFactCard";
import { RetrievalPanel } from "@/features/evidence/RetrievalPanel";

export function CasePage() {
  return (
    <div className="space-y-4">
      <div className="grid items-start gap-4 xl:grid-cols-[440px_minmax(0,1fr)]">
        <div className="order-2 space-y-4 xl:order-1">
          <CaseOverview />
          <FactPanel />
          <MissingFactCard />
          <RecidivismPanel />
        </div>
        <div className="order-1 xl:sticky xl:top-20 xl:order-2">
          <ConversationPanel />
        </div>
      </div>
      <RetrievalPanel />
      <EvidencePanel />
      <AssessmentEntry />
    </div>
  );
}
