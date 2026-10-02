import { useEffect, useRef } from "react";

import { MessageBubble } from "@/features/conversation/MessageBubble";
import type { ChatMessage } from "@/types/api";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  if (!messages.length) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <div>
          <p className="text-sm font-medium text-neutral-900">Bắt đầu bằng điều đã biết</p>
          <p className="mt-1 text-sm text-neutral-600">
            Trợ lý sẽ hỏi phần còn thiếu. Câu trả lời nằm trong hội thoại này, không phải một biểu mẫu cho từng mục.
          </p>
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
