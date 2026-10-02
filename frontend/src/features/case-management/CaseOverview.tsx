import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { familyLabel } from "@/lib/labels";
import { formatDate } from "@/lib/utils";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

export function CaseOverview() {
  const { caseView, facts } = useWorkspace();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Thông tin hồ sơ</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Info label="Nhân viên" value={caseView.employee_name || "—"} />
        <Info label="Mã nhân viên" value={caseView.employee_code || "—"} />
        <Info label="Ngày xảy ra" value={formatDate(caseView.incident_date)} />
        <Info label="Nhóm tình tiết" value={familyLabel(facts?.family)} />
        <div>
          <p className="text-xs text-neutral-500">Mô tả</p>
          <p className="mt-1 whitespace-pre-wrap text-neutral-800">{caseView.description || "—"}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-neutral-500">{label}</p>
      <p className="font-medium text-neutral-900">{value}</p>
    </div>
  );
}
