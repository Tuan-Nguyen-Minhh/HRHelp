import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

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
  const minutes = answer?.drafts.find((item) => item.draft_type === "MINUTES");
  const report = answer?.message?.includes("BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC") ? answer.message : null;
  const body = report || minutes?.content;
  if (!body) return null;
  const canSend = answer?.ticket?.disposition === "PREVIEW";

  function choose(action: HrAction) {
    setChoice(action);
    if (action === "REQUEST_MORE_INFORMATION") focusChat();
  }

  return (
    <Card id="bien-ban" className="scroll-mt-4 border-sky-200">
      <CardHeader>
        <CardTitle>Biên bản đánh giá vụ việc</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-neutral-700">
          Biên bản gom tình tiết đã xác nhận, đoạn đã truy xuất và mức xử lý đề xuất. HR đọc bản này rồi chọn bước tiếp theo. Phiếu pháp chế được tạo sau khi HR chọn gửi và backend đang mở phiếu.
        </p>
        <h3 className="font-medium text-neutral-900">{report ? "Biên bản đánh giá" : minutes?.title}</h3>
        <p className="whitespace-pre-wrap leading-6 text-neutral-800">{body}</p>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Quyết định của HR">
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
