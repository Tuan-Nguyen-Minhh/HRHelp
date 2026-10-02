import { MessageSquareText, Sparkles } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { MessageInput } from "@/features/conversation/MessageInput";
import { MessageList } from "@/features/conversation/MessageList";

export function ConversationPanel() {
  const { messages } = useWorkspace();
  return (
    <Card className="flex min-h-[520px] flex-col overflow-hidden border-[#d8e9ee] bg-[#f7fbfd] shadow-sm xl:max-h-[calc(100vh-6rem)]">
      <CardHeader className="border-b border-[#d8e9ee] bg-white/90">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-14 w-14 shrink-0 items-end justify-center overflow-hidden rounded-2xl border border-[#cfe5ec] bg-[#e7f7fb] shadow-sm">
              <img className="h-full w-full object-cover object-top" src="/legal-agent-avatar.png" alt="Agent pháp chế" />
            </span>
            <div>
              <CardTitle>Agent pháp chế</CardTitle>
              <p className="mt-1 text-xs leading-5 text-[#4d7380]">
                Hỏi phần còn thiếu, gợi ý căn cứ và giữ hội thoại dễ tra lại. Người phụ trách vẫn là người duyệt cuối.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 font-medium text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Đang sẵn sàng
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 font-medium text-[#007c9d]">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Có ngữ cảnh hồ sơ
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
        <div className="h-full min-h-[260px] overflow-y-auto px-4 py-5 md:px-6 xl:max-h-[calc(100vh-22rem)]">
          <MessageList messages={messages} />
          {messages.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {["Tóm tắt tình tiết", "Cần bổ sung chứng cứ gì?", "Kiểm tra rủi ro quy trình"].map((item) => (
                <span key={item} className="inline-flex items-center gap-1.5 rounded-full border border-[#cfe5ec] bg-white px-3 py-1.5 text-xs font-medium text-[#315867] shadow-sm">
                  <MessageSquareText className="h-3.5 w-3.5 text-[#009ec1]" aria-hidden="true" />
                  {item}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </CardContent>
      <MessageInput />
    </Card>
  );
}
