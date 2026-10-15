import { AlertTriangle, Check, Circle } from "lucide-react";

import { workflowSteps, type StepState } from "@/lib/workflow";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

const STATE_LABEL: Record<StepState, string> = {
  completed: "Xong",
  active: "Đang thực hiện",
  waiting: "Chưa tới",
  blocked: "Cần xem xét",
};

export function CaseProgress() {
  const { caseView, answer } = useWorkspace();
  const steps = workflowSteps(caseView.status, answer?.ticket?.disposition ?? null);
  return (
    <section className="rounded-lg border border-rule bg-white px-2 py-3 sm:px-3" aria-label="Tiến độ hồ sơ">
      <p className="px-1 text-xs font-semibold tracking-wide text-ink-3">TIẾN ĐỘ</p>
      <ol className="mt-2 grid gap-1 sm:gap-2" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
        {steps.map((step, index) => (
          <li key={step.id} aria-current={step.state === "active" ? "step" : undefined} className="flex min-w-0 flex-col items-center gap-1.5 rounded-md border border-rule px-1 py-2 text-center sm:flex-row sm:text-left">
            <StepMark state={step.state} index={index + 1} />
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="flex min-h-8 items-center justify-center break-words text-[11px] font-medium leading-4 text-ink sm:min-h-0 sm:justify-start">{step.label}</span>
              <span className="mt-auto block break-words text-[10px] leading-3 text-ink-3">{STATE_LABEL[step.state]}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function StepMark({ state, index }: { state: StepState; index: number }) {
  const className = cn(
    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px]",
    state === "completed" && "border-leather bg-leather text-paper",
    state === "active" && "border-son bg-paper-2 text-son-dark",
    state === "waiting" && "border-rule-2 bg-white text-ink-3",
    state === "blocked" && "border-son bg-son-tint text-son-dark",
  );
  return (
    <span className={className} aria-hidden="true">
      {state === "completed" ? <Check className="h-3.5 w-3.5" /> : null}
      {state === "blocked" ? <AlertTriangle className="h-3.5 w-3.5" /> : null}
      {state === "active" || state === "waiting" ? state === "waiting" ? <Circle className="h-3 w-3" /> : index : null}
    </span>
  );
}
