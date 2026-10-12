import { AdministrativeSection, PrecedentSection } from "@/features/assessment/LayerNotes";
import { ProcedureAssessment } from "@/features/assessment/ProcedureAssessment";
import { RiskAssessment } from "@/features/assessment/RiskAssessment";
import { ReviewMinutes } from "@/features/assessment/ReviewMinutes";
import { SanctionAssessment } from "@/features/assessment/SanctionAssessment";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { visibleReportText } from "@/lib/report";
import { assessmentView } from "@/lib/workflow";

export function AssessmentPanel() {
  const { answer, answerLoading, answerError, facts, caseView } = useWorkspace();
  const view = assessmentView(caseView.status, answer, facts?.missing_fact_keys.length ?? 0);
  const showReport = Boolean(answer) && view !== "collecting";
  const savedReport = visibleReportText(answer?.message);

  return (
    <section className="space-y-4" aria-label="Đánh giá căn cứ">
      <div>
        <h2 className="text-sm font-semibold tracking-wide text-ink-3">ĐÁNH GIÁ VÀ CĂN CỨ</h2>
        <p className="mt-1 text-sm text-ink-2">Tình tiết → Đối chiếu → Căn cứ đã lấy → Đánh giá đã lưu</p>
      </div>
      {answerLoading ? <p className="text-sm text-ink-2">Đang tải báo cáo…</p> : null}
      {answerError ? <p className="text-sm text-son-dark">{answerError}</p> : null}
      <SanctionAssessment />
      <ReviewMinutes />
      {showReport ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <ProcedureAssessment />
            <RiskAssessment />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <PrecedentSection />
            <AdministrativeSection />
          </div>
          {savedReport ? (
            <details className="rounded-lg border border-rule bg-white px-4 py-3 text-sm">
              <summary className="cursor-pointer font-medium">Nội dung báo cáo đã lưu</summary>
              <p className="mt-3 whitespace-pre-wrap leading-6 text-ink">{savedReport}</p>
            </details>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
