import { useEffect, useRef } from "react";
import { CheckCircle2 } from "lucide-react";

import { MessageBubble } from "@/features/conversation/MessageBubble";
import type { ChatMessage } from "@/types/api";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  if (!messages.length) {
    return (
      <div className="px-1">
        <div className="max-w-xl rounded-3xl border border-[#d8e9ee] bg-white p-5 text-left shadow-sm">
          <div className="flex h-20 w-20 items-end justify-center overflow-hidden rounded-3xl border border-[#cfe5ec] bg-[#e7f7fb] shadow-sm">
            <img className="h-full w-full object-cover object-top" src="/legal-agent-avatar.png" alt="Agent pháp chế" />
          </div>
          <p className="mt-4 text-sm font-semibold text-[#073642]">Agent pháp chế đã sẵn sàng</p>
          <p className="mt-2 text-sm leading-6 text-[#4d7380]">
            Bắt đầu bằng điều đã biết. Agent sẽ hỏi phần còn thiếu và giữ câu trả lời trong hội thoại này.
          </p>
          <div className="mt-4 grid gap-2 text-left text-xs text-[#4d7380]">
            {["Mô tả sự việc chính", "Nêu mốc thời gian", "Đính hướng chứng cứ cần kiểm tra"].map((item) => (
              <div key={item} className="flex items-center gap-2 rounded-full bg-[#f3f9fb] px-3 py-2">
                <CheckCircle2 className="h-4 w-4 text-[#009ec1]" aria-hidden="true" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" aria-live="polite">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
