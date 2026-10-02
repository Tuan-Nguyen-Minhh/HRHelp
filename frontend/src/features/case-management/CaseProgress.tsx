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
    <section className="rounded-lg border border-neutral-200 bg-white px-3 py-3" aria-label="Tiến độ hồ sơ">
      <p className="px-1 text-xs font-semibold tracking-wide text-neutral-500">TIẾN ĐỘ</p>
      <ol className="mt-2 flex gap-2 overflow-x-auto pb-1">
        {steps.map((step, index) => (
          <li key={step.id} className="flex min-w-40 items-center gap-2 rounded-md border border-neutral-200 px-2 py-2">
            <StepMark state={step.state} index={index + 1} />
            <span>
              <span className="block text-sm font-medium text-neutral-900">{step.label}</span>
              <span className="block text-xs text-neutral-500">{STATE_LABEL[step.state]}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function StepMark({ state, index }: { state: StepState; index: number }) {
  const className = cn(
    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs",
    state === "completed" && "border-emerald-700 bg-emerald-700 text-white",
    state === "active" && "border-[#009EC1] bg-[#e7f6f9] text-[#009EC1]",
    state === "waiting" && "border-neutral-300 bg-white text-neutral-500",
    state === "blocked" && "border-red-700 bg-red-50 text-red-800",
  );
  return (
    <span className={className} aria-hidden="true">
      {state === "completed" ? <Check className="h-3.5 w-3.5" /> : null}
      {state === "blocked" ? <AlertTriangle className="h-3.5 w-3.5" /> : null}
      {state === "active" || state === "waiting" ? state === "waiting" ? <Circle className="h-3 w-3" /> : index : null}
    </span>
  );
}
