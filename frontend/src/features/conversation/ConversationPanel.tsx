import { MessageSquareText } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { MessageInput } from "@/features/conversation/MessageInput";
import { MessageList } from "@/features/conversation/MessageList";

export function ConversationPanel() {
  const { messages } = useWorkspace();
  return (
    <Card className="flex min-h-[520px] flex-col overflow-hidden shadow-sm xl:max-h-[calc(100vh-6rem)]">
      <CardHeader className="border-b border-rule bg-paper px-4 py-3 md:px-5">
        <div className="flex w-full items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-end justify-center overflow-hidden rounded-lg border border-rule bg-paper-2">
            <img className="h-full w-full object-cover object-top" src="/legal-agent-avatar.png" alt="" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <CardTitle>Agent pháp chế</CardTitle>
            <p className="truncate text-xs text-ink-3">Hỏi phần còn thiếu, gợi ý căn cứ.</p>
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full border border-rule bg-paper-2 px-2.5 py-1 text-[11px] font-medium text-ink-2">
              <span className="h-1.5 w-1.5 rounded-full bg-son" aria-hidden="true" />
              Sẵn sàng
            </span>
            <span className="hidden rounded-full border border-rule bg-paper px-2.5 py-1 text-[11px] font-medium text-ink-3 sm:inline">
              Có ngữ cảnh hồ sơ
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden bg-paper-2/40 p-0">
        <div className="h-full min-h-[260px] overflow-y-auto px-4 py-5 md:px-6 xl:max-h-[calc(100vh-22rem)]">
          <MessageList messages={messages} />
          {messages.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {["Tóm tắt tình tiết", "Cần bổ sung chứng cứ gì?", "Kiểm tra rủi ro quy trình"].map((item) => (
                <span key={item} className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-paper px-3 py-1.5 text-xs font-medium text-ink-2">
                  <MessageSquareText className="h-3.5 w-3.5 text-son" aria-hidden="true" />
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
