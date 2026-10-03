import { useState } from "react";
import { Download } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { api, errorMessage } from "@/services/api";
import { visibleReportText } from "@/lib/report";

const ACTIONS = [
  { code: "CONTINUE", label: "HR đồng ý với đánh giá" },
  { code: "REQUEST_MORE_INFORMATION", label: "HR yêu cầu bổ sung thông tin" },
  { code: "SEND_TO_LEGAL", label: "HR gửi hồ sơ cho pháp chế" },
  { code: "REJECT_ASSESSMENT", label: "HR không sử dụng kết quả đánh giá này" },
] as const;

type HrAction = (typeof ACTIONS)[number]["code"];

export function ReviewMinutes() {
  const { answer, caseId, focusChat } = useWorkspace();
  const [choice, setChoice] = useState<HrAction | null>(null);
  const [exportNote, setExportNote] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const minutes = answer?.drafts.find((item) => item.draft_type === "MINUTES");
  const report = answer?.message?.includes("BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC") ? visibleReportText(answer.message) : null;
  const body = report || minutes?.content || null;
  if (!body) return null;
  const canSend = answer?.ticket?.disposition === "PREVIEW";

  function choose(action: HrAction) {
    setChoice(action);
    if (action === "REQUEST_MORE_INFORMATION") focusChat();
  }

  async function exportWord() {
    setExporting(true);
    setExportNote(null);
    try {
      const payload = await api.exportCase(caseId, "assessment", "docx");
      const content = typeof payload.content === "object" && payload.content !== null ? payload.content : {};
      const fileName = "file_name" in content && typeof content.file_name === "string" ? content.file_name : "biên bản Word";
      const path = "path" in content && typeof content.path === "string" ? content.path : "";
      setExportNote(path ? `Đã tạo ${fileName}: ${path}` : `Đã tạo ${fileName}.`);
    } catch (error) {
      setExportNote(errorMessage(error));
    } finally {
      setExporting(false);
    }
  }

  return (
    <Card id="bien-ban" className="scroll-mt-4 border-sky-200">
      <CardHeader>
        <div>
          <CardTitle>Biên bản đánh giá vụ việc</CardTitle>
        </div>
        <Button variant="outline" size="sm" onClick={() => void exportWord()} disabled={exporting}>
          <Download className="h-4 w-4" aria-hidden />
          {exporting ? "Đang xuất…" : "Xuất Word"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-neutral-700">
          Biên bản gom tình tiết đã xác nhận, đoạn đã truy xuất và mức xử lý đề xuất. HR có thể mở bản biểu mẫu để xem trước, sửa tay rồi mới xác nhận hoặc xuất Word.
        </p>
        <h3 className="font-medium text-neutral-900">{report ? "Biên bản đánh giá" : minutes?.title}</h3>
        <p className="whitespace-pre-wrap leading-6 text-neutral-800">{body}</p>
        {exportNote ? <p className="rounded-md border border-sky-100 bg-sky-50 px-3 py-2 text-xs text-[#276274]">{exportNote}</p> : null}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Quyết định của HR">
          <Button asChild variant="secondary">
            <Link to={`/cases/${caseId}/assessment`}>Mở biên bản để sửa</Link>
          </Button>
          {ACTIONS.map((action) =>
            action.code === "SEND_TO_LEGAL" && canSend ? (
              <Button key={action.code} asChild>
                <Link to={`/cases/${caseId}/decision`}>{action.label}</Link>
              </Button>
            ) : (
              <Button key={action.code} variant="outline" onClick={() => choose(action.code)}>
                {action.label}
              </Button>
            ),
          )}
        </div>
        {choice ? <p className="text-xs text-neutral-600">{choiceNote(choice, canSend)}</p> : null}
      </CardContent>
    </Card>
  );
}

function choiceNote(choice: HrAction, canSend: boolean): string {
  if (choice === "CONTINUE") {
    return "Đã ghi nhận HR đồng ý với đánh giá. Phiếu pháp chế vẫn đóng.";
  }
  if (choice === "REQUEST_MORE_INFORMATION") {
    return "Hãy bổ sung tình tiết trong hội thoại. Phiếu pháp chế vẫn đóng.";
  }
  if (choice === "REJECT_ASSESSMENT") {
    return "Đã ghi nhận HR không sử dụng kết quả này. Phiếu pháp chế vẫn đóng.";
  }
  if (canSend) {
    return "Mẫu mã pháp chế là bước gửi hồ sơ. Phiếu được ghi khi HR gửi mẫu đó.";
  }
  return "Đã ghi nhận yêu cầu gửi pháp chế. Backend đang giữ hồ sơ, nên phiếu chưa được tạo.";
}
