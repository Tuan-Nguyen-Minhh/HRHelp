import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToneBadge } from "@/components/common/StatusBadge";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { riskLabel, riskTone } from "@/lib/labels";

export function RiskAssessment() {
  const { answer } = useWorkspace();
  const level = answer?.risk_level ?? null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rủi ro căn cứ</CardTitle>
        <ToneBadge tone={riskTone(level)} label={`${riskLabel(level)}${level ? ` · ${level}` : ""}`} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="text-neutral-700">Mức này là độ chắc của căn cứ và của đánh giá đã lưu.</p>
        <p className="text-xs text-neutral-500">Lý do nằm ở thẻ đánh giá chế tài, đúng văn bản backend đã ghi.</p>
      </CardContent>
    </Card>
  );
}
