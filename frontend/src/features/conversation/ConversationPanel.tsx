import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { MessageInput } from "@/features/conversation/MessageInput";
import { MessageList } from "@/features/conversation/MessageList";

export function ConversationPanel() {
  const { messages } = useWorkspace();
  return (
    <Card className="flex min-h-[520px] flex-col">
      <CardHeader>
        <div>
          <CardTitle>Hội thoại</CardTitle>
          <p className="mt-1 text-xs text-[#4d7380]">
            AI hỏi phần còn thiếu. Câu trả lời lấy từ hội thoại đã lưu. AI không duyệt và không ký.
          </p>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden">
        <div className="h-[min(560px,calc(100vh-22rem))] overflow-y-auto">
          <MessageList messages={messages} />
        </div>
      </CardContent>
      <MessageInput />
    </Card>
  );
}
