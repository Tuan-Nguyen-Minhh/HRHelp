import { Check, Circle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

export function ProcedureAssessment() {
  const { answer } = useWorkspace();
  const steps = answer?.process_steps ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Thủ tục xử lý kỷ luật</CardTitle>
      </CardHeader>
      <CardContent>
        {steps.length === 0 ? (
          <p className="text-sm text-ink-2">Chưa có bước thủ tục trên báo cáo.</p>
        ) : (
          <ul className="space-y-3">
            {steps.map((step) => {
              const Icon = step.done ? Check : Circle;
              return (
                <li key={step.code} className="flex gap-2 text-sm">
                  <Icon className={`mt-0.5 h-4 w-4 ${step.done ? "text-ink-2" : "text-ink-4"}`} aria-hidden="true" />
                  <span>
                    <span className="block font-medium">{step.label}</span>
                    <span className="text-xs text-ink-3">{step.done ? "Đã có" : "Chưa có"} · {step.code}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-3 text-xs text-ink-3">
          Mỗi bước lấy từ process_steps của báo cáo. Payload không kèm mã đoạn riêng cho từng bước.
        </p>
      </CardContent>
    </Card>
  );
}
